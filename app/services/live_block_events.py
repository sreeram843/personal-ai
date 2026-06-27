"""SSE/stream callbacks for live content blocks emitted during tool runs."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Awaitable, Callable, List, Optional

from app.schemas.content_block import ContentBlock

BlockEventCallback = Callable[[ContentBlock], Awaitable[None] | None]

_block_callbacks: ContextVar[List[BlockEventCallback]] = ContextVar("block_event_callbacks", default=[])


def activate_block_event_callbacks(callbacks: List[BlockEventCallback]) -> Token:
    return _block_callbacks.set(list(callbacks))


def deactivate_block_event_callbacks(token: Token) -> None:
    _block_callbacks.reset(token)


async def emit_live_block_event(block: ContentBlock) -> None:
    for callback in _block_callbacks.get():
        try:
            result = callback(block)
            if hasattr(result, "__await__"):
                await result
        except Exception:
            continue


__all__ = [
    "BlockEventCallback",
    "activate_block_event_callbacks",
    "deactivate_block_event_callbacks",
    "emit_live_block_event",
]
