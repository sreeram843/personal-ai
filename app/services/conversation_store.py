from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, MessageRole, User
from app.schemas.chat import ChatRequest, ChatResponse


def list_conversations_for_user(db: Session, user_id: uuid.UUID) -> List[Tuple[Conversation, int]]:
    stmt = (
        select(Conversation, func.count(Message.id))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(
            Conversation.pinned_at.is_(None),
            Conversation.pinned_at.desc(),
            Conversation.updated_at.desc(),
        )
    )
    return list(db.execute(stmt).all())


def create_conversation(
    db: Session,
    user: User,
    *,
    title: Optional[str] = None,
    mode: Optional[str] = "smart",
    assistant_id: Optional[str] = None,
) -> Conversation:
    normalized_assistant = (assistant_id or "").strip()
    if normalized_assistant in {"", "default"}:
        normalized_assistant = None
    conversation = Conversation(
        user_id=user.id,
        title=title or "New conversation",
        mode=mode or "smart",
        assistant_id=normalized_assistant,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_for_user(
    db: Session,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Optional[Conversation]:
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )


def list_messages_for_conversation(
    db: Session,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Optional[List[Message]]:
    conversation = get_conversation_for_user(db, user_id, conversation_id)
    if conversation is None:
        return None
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        ).all()
    )


def delete_conversation_for_user(
    db: Session,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    conversation = get_conversation_for_user(db, user_id, conversation_id)
    if conversation is None:
        return False
    db.delete(conversation)
    db.commit()
    return True


def update_conversation_for_user(
    db: Session,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    title: Optional[str] = None,
    pinned: Optional[bool] = None,
    assistant_id: Optional[str] = None,
) -> Optional[Conversation]:
    conversation = get_conversation_for_user(db, user_id, conversation_id)
    if conversation is None:
        return None

    if title is not None:
        normalized = title.strip()
        conversation.title = normalized[:255] if normalized else "New conversation"

    if pinned is not None:
        conversation.pinned_at = datetime.now(timezone.utc) if pinned else None

    if assistant_id is not None:
        normalized_assistant = assistant_id.strip()
        conversation.assistant_id = normalized_assistant or None

    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _parse_conversation_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation_id") from exc


def resolve_conversation_for_chat(
    db: Session,
    user: User,
    payload: ChatRequest,
    *,
    mode: str,
) -> Conversation:
    if payload.conversation_id:
        conversation = get_conversation_for_user(db, user.id, _parse_conversation_id(payload.conversation_id))
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return conversation

    from app.services.skill_resolution import assistant_id_from_options

    return create_conversation(
        db,
        user,
        mode=mode,
        assistant_id=assistant_id_from_options(payload.options),
    )


def _touch_conversation(db: Session, conversation: Conversation) -> None:
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(conversation)


def maybe_set_title_from_user_message(db: Session, conversation: Conversation, content: str) -> None:
    trimmed = content.strip()
    if not trimmed:
        return
    if conversation.title in {None, "", "New conversation"}:
        conversation.title = trimmed[:255]
        db.add(conversation)


def append_message(
    db: Session,
    conversation: Conversation,
    *,
    role: MessageRole,
    content: str,
    metadata: Optional[dict] = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        metadata_json=metadata,
    )
    db.add(message)
    _touch_conversation(db, conversation)
    db.commit()
    db.refresh(message)
    return message


def persist_user_turn(db: Session, conversation: Conversation, content: str) -> Message:
    maybe_set_title_from_user_message(db, conversation, content)
    db.commit()
    db.refresh(conversation)
    return append_message(db, conversation, role=MessageRole.user, content=content)


def _assistant_metadata(response: ChatResponse, *, mode: str) -> dict:
    metadata = {"mode": mode}
    if response.latency_ms is not None:
        metadata["latency_ms"] = response.latency_ms
    if response.sources:
        metadata["sources"] = [source.model_dump() for source in response.sources]
    if response.workflow:
        metadata["workflow"] = response.workflow.model_dump()
    if response.reasoning:
        metadata["reasoning"] = response.reasoning
    if response.sentiment:
        metadata["sentiment"] = response.sentiment
    if response.prompt_tokens is not None:
        metadata["prompt_tokens"] = response.prompt_tokens
    if response.completion_tokens is not None:
        metadata["completion_tokens"] = response.completion_tokens
    if response.blocks:
        metadata["blocks"] = [block.model_dump() for block in response.blocks]
    if response.live:
        metadata["live"] = response.live.model_dump()
    return metadata


def _patch_last_user_message_prompt_tokens(
    db: Session,
    conversation: Conversation,
    prompt_tokens: int,
) -> None:
    last_user = db.scalar(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.user,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if last_user is None:
        return
    metadata = dict(last_user.metadata_json or {})
    metadata["prompt_tokens"] = prompt_tokens
    last_user.metadata_json = metadata
    db.add(last_user)


def persist_assistant_turn(
    db: Session,
    conversation: Conversation,
    response: ChatResponse,
    *,
    mode: str,
) -> Message:
    if response.prompt_tokens is not None:
        _patch_last_user_message_prompt_tokens(db, conversation, response.prompt_tokens)
    message = append_message(
        db,
        conversation,
        role=MessageRole.assistant,
        content=response.message,
        metadata=_assistant_metadata(response, mode=mode),
    )
    return message


def attach_conversation_id(response: ChatResponse, conversation: Conversation) -> ChatResponse:
    return response.model_copy(update={"conversation_id": str(conversation.id)})

