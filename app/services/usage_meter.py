"""Request-scoped LLM usage context (user + route) for metering."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

from app.db.models import LlmUsageEvent
from app.db.session import get_session_factory

logger = logging.getLogger(__name__)

_usage_user_id: ContextVar[Optional[uuid.UUID]] = ContextVar("usage_user_id", default=None)
_usage_route: ContextVar[str] = ContextVar("usage_route", default="chat")


def set_usage_context(*, user_id: Optional[uuid.UUID] = None, route: str = "chat") -> None:
    _usage_user_id.set(user_id)
    _usage_route.set(route or "chat")


def clear_usage_context() -> None:
    _usage_user_id.set(None)
    _usage_route.set("chat")


def record_llm_usage(
    *,
    provider: str,
    model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
) -> None:
    prompt = int(prompt_tokens or 0)
    completion = int(completion_tokens or 0)
    total = prompt + completion
    if total <= 0 and prompt == 0 and completion == 0:
        return
    user_id = _usage_user_id.get()
    route = _usage_route.get() or "chat"
    try:
        session = get_session_factory()()
        try:
            session.add(
                LlmUsageEvent(
                    user_id=user_id,
                    provider=provider,
                    model=model,
                    route=route,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.exception("Failed to record LLM usage event")


__all__ = [
    "clear_usage_context",
    "record_llm_usage",
    "set_usage_context",
]
