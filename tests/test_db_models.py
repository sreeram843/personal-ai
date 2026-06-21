"""Tests for SQLAlchemy models and database session."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Conversation, Document, Message, MessageRole, User


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_user_conversation_message_relationships(db_session: Session) -> None:
    user = User(email="alice@example.com", display_name="Alice")
    conversation = Conversation(user=user, title="Planning", mode="smart")
    conversation.messages.append(
        Message(role=MessageRole.user, content="Hello"),
    )
    conversation.messages.append(
        Message(role=MessageRole.assistant, content="Hi Alice", metadata_json={"sources": []}),
    )
    db_session.add(user)
    db_session.commit()

    stored_user = db_session.scalar(select(User).where(User.email == "alice@example.com"))
    assert stored_user is not None
    assert len(stored_user.conversations) == 1
    assert stored_user.conversations[0].title == "Planning"
    assert len(stored_user.conversations[0].messages) == 2
    assert stored_user.conversations[0].messages[1].role == MessageRole.assistant


def test_user_document_scoped_to_owner(db_session: Session) -> None:
    user_a = User(email="a@example.com")
    user_b = User(email="b@example.com")
    user_a.documents.append(Document(title="private-notes.txt", qdrant_point_id="pt-1"))
    user_b.documents.append(Document(title="other.txt", qdrant_point_id="pt-2"))
    db_session.add_all([user_a, user_b])
    db_session.commit()

    docs_for_a = db_session.scalars(select(Document).where(Document.user_id == user_a.id)).all()
    assert len(docs_for_a) == 1
    assert docs_for_a[0].title == "private-notes.txt"


def test_conversation_cascade_delete_removes_messages(db_session: Session) -> None:
    user = User(external_id="dev-user")
    conversation = Conversation(user=user, title="Temp")
    conversation.messages.append(Message(role=MessageRole.user, content="one"))
    db_session.add(user)
    db_session.commit()

    conversation_id = conversation.id
    db_session.delete(conversation)
    db_session.commit()

    remaining = db_session.scalars(select(Message).where(Message.conversation_id == conversation_id)).all()
    assert remaining == []


def test_models_use_uuid_primary_keys(db_session: Session) -> None:
    user = User()
    db_session.add(user)
    db_session.commit()
    assert isinstance(user.id, uuid.UUID)
