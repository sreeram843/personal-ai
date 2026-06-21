from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Conversation, User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.conversation_store import (
    attach_conversation_id,
    persist_assistant_turn,
    persist_user_turn,
    resolve_conversation_for_chat,
)
from app.services.chat_messages import get_last_user_message
from app.services.llm_metrics import observe_chat_request


async def run_persisted_chat(
    *,
    db: Session,
    user: User,
    payload: ChatRequest,
    mode: str,
    handler: Callable[[ChatRequest, Conversation], Awaitable[ChatResponse]],
) -> ChatResponse:
    conversation = resolve_conversation_for_chat(db, user, payload, mode=mode)
    user_message = get_last_user_message(payload)
    persist_user_turn(db, conversation, user_message.content)
    payload.conversation_id = str(conversation.id)

    async with observe_chat_request(mode=mode):
        response = await handler(payload, conversation)
    persist_assistant_turn(db, conversation, response, mode=mode)
    return attach_conversation_id(response, conversation)


def _parse_sse_event(event: str) -> dict[str, Any] | None:
    import json

    prefix = "data: "
    if not event.startswith(prefix):
        return None
    body = event[len(prefix) :].strip()
    if not body:
        return None
    parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else None


def inject_conversation_id_into_sse_event(event: str, conversation_id: str) -> str:
    """Add conversation_id to the JSON payload of a final SSE event."""
    import json

    prefix = "data: "
    if not event.startswith(prefix):
        return event
    body = event[len(prefix) :].strip()
    if not body:
        return event
    payload: dict[str, Any] = json.loads(body)
    if payload.get("type") == "final" and isinstance(payload.get("response"), dict):
        payload["response"]["conversation_id"] = conversation_id
    return f"data: {json.dumps(payload)}\n\n"


async def wrap_chat_stream_with_persistence(
    *,
    db: Session,
    user: User,
    payload: ChatRequest,
    mode: str,
    stream_factory: Callable[[ChatRequest], AsyncIterator[str]],
) -> AsyncIterator[str]:
    conversation = resolve_conversation_for_chat(db, user, payload, mode=mode)
    user_message = get_last_user_message(payload)
    persist_user_turn(db, conversation, user_message.content)
    payload.conversation_id = str(conversation.id)

    async for event in stream_factory(payload):
        parsed = _parse_sse_event(event)
        if parsed and parsed.get("type") == "final" and isinstance(parsed.get("response"), dict):
            response = ChatResponse(**parsed["response"])
            persist_assistant_turn(db, conversation, response, mode=mode)
            yield inject_conversation_id_into_sse_event(event, str(conversation.id))
            continue
        yield event


def persist_stream_final_response(
    db: Session,
    conversation: Conversation,
    response: ChatResponse,
    *,
    mode: str,
) -> ChatResponse:
    persist_assistant_turn(db, conversation, response, mode=mode)
    return attach_conversation_id(response, conversation)
