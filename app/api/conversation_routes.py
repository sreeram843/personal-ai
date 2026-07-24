from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.db.models import Message
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationSummary,
    CreateConversationRequest,
    StoredMessageResponse,
    UpdateConversationRequest,
)
from app.services.conversation_store import (
    create_conversation,
    delete_conversation_for_user,
    list_conversations_for_user,
    list_messages_for_conversation,
    update_conversation_for_user,
)
from app.services.audit_log import record_audit

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _message_count(db: Session, conversation_id: uuid.UUID) -> int:
    return int(
        db.scalar(select(func.count(Message.id)).where(Message.conversation_id == conversation_id)) or 0
    )


def _to_summary(conversation, message_count: int) -> ConversationSummary:
    return ConversationSummary(
        id=str(conversation.id),
        title=conversation.title,
        mode=conversation.mode,
        assistant_id=conversation.assistant_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count,
        pinned=conversation.pinned_at is not None,
        pinned_at=conversation.pinned_at,
    )


def _to_message(message) -> StoredMessageResponse:
    return StoredMessageResponse(
        id=str(message.id),
        role=message.role.value,
        content=message.content,
        metadata=message.metadata_json or {},
        created_at=message.created_at,
    )


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    rows = list_conversations_for_user(db, user.id)
    return ConversationListResponse(
        conversations=[_to_summary(conversation, message_count) for conversation, message_count in rows]
    )


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def create_conversation_route(
    body: CreateConversationRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ConversationSummary:
    conversation = create_conversation(
        db,
        user,
        title=body.title,
        mode=body.mode,
        assistant_id=body.assistant_id,
    )
    return _to_summary(conversation, 0)


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def update_conversation_route(
    conversation_id: uuid.UUID,
    body: UpdateConversationRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ConversationSummary:
    if body.title is None and body.pinned is None and body.assistant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of title, pinned, or assistant_id is required",
        )

    conversation = update_conversation_for_user(
        db,
        user.id,
        conversation_id,
        title=body.title,
        pinned=body.pinned,
        assistant_id=body.assistant_id,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return _to_summary(conversation, _message_count(db, conversation.id))


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
def list_conversation_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ConversationMessagesResponse:
    messages = list_messages_for_conversation(db, user.id, conversation_id)
    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationMessagesResponse(
        conversation_id=str(conversation_id),
        messages=[_to_message(message) for message in messages],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_route(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Response:
    deleted = delete_conversation_for_user(db, user.id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    record_audit(
        "conversation.delete",
        user_id=str(user.id),
        detail={"conversation_id": str(conversation_id)},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
