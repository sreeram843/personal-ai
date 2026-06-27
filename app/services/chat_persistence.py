from __future__ import annotations

import json
import time
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


def _apply_conversation_context(payload: ChatRequest, conversation: Conversation) -> None:
    options = dict(payload.options or {})
    if conversation.assistant_id:
        options.setdefault("assistant_id", conversation.assistant_id)
    payload.options = options


def _record_user_memory(*, user_id: str, user_message: str, assistant_message: str) -> None:
    from app.services.chat_execution import record_post_chat_memory

    record_post_chat_memory(
        user_id=user_id,
        user_message=user_message,
        assistant_message=assistant_message,
    )


async def run_persisted_chat(
    *,
    db: Session,
    user: User,
    payload: ChatRequest,
    mode: str,
    handler: Callable[[ChatRequest, Conversation], Awaitable[ChatResponse]],
) -> ChatResponse:
    conversation = resolve_conversation_for_chat(db, user, payload, mode=mode)
    _apply_conversation_context(payload, conversation)
    user_message = get_last_user_message(payload)
    persist_user_turn(db, conversation, user_message.content)
    payload.conversation_id = str(conversation.id)

    started = time.perf_counter()
    async with observe_chat_request(mode=mode):
        response = await handler(payload, conversation)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response = response.model_copy(update={"latency_ms": elapsed_ms})
    persist_assistant_turn(db, conversation, response, mode=mode)
    _record_user_memory(
        user_id=str(user.id),
        user_message=user_message.content,
        assistant_message=response.message,
    )
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


def inject_conversation_id_into_sse_event(
    event: str,
    conversation_id: str,
    *,
    latency_ms: float | None = None,
) -> str:
    """Add conversation_id (and optional latency) to the JSON payload of a final SSE event."""
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
        if latency_ms is not None:
            payload["response"]["latency_ms"] = latency_ms
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
    _apply_conversation_context(payload, conversation)
    user_message = get_last_user_message(payload)
    persist_user_turn(db, conversation, user_message.content)
    payload.conversation_id = str(conversation.id)

    yield f"data: {json.dumps({'type': 'conversation', 'conversation_id': str(conversation.id)})}\n\n"

    started = time.perf_counter()
    async for event in stream_factory(payload):
        parsed = _parse_sse_event(event)
        if parsed and parsed.get("type") == "final" and isinstance(parsed.get("response"), dict):
            elapsed_ms = (time.perf_counter() - started) * 1000
            response = ChatResponse(**parsed["response"]).model_copy(update={"latency_ms": elapsed_ms})
            persist_assistant_turn(db, conversation, response, mode=mode)
            _record_user_memory(
                user_id=str(user.id),
                user_message=user_message.content,
                assistant_message=response.message,
            )
            yield inject_conversation_id_into_sse_event(
                event,
                str(conversation.id),
                latency_ms=elapsed_ms,
            )
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
