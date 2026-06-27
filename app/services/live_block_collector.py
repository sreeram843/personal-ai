from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from typing import List

from app.schemas.content_block import ContentBlock

from app.services.live_block_events import emit_live_block_event

_live_blocks: ContextVar[List[ContentBlock]] = ContextVar("live_blocks", default=[])


def reset_live_blocks() -> Token:
    return _live_blocks.set([])


def restore_live_blocks(token: Token) -> None:
    _live_blocks.reset(token)


def append_live_block(block: ContentBlock) -> None:
    if block is None:
        return
    blocks = list(_live_blocks.get())
    blocks.append(block)
    _live_blocks.set(blocks)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(emit_live_block_event(block))
    except RuntimeError:
        pass


def get_live_blocks() -> List[ContentBlock]:
    return list(_live_blocks.get())


__all__ = ["append_live_block", "get_live_blocks", "reset_live_blocks", "restore_live_blocks"]
