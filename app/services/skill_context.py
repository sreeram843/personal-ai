"""Active skill tool filter for agent runs."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional, Set

_skill_allowed_tools: ContextVar[Optional[Set[str]]] = ContextVar("skill_allowed_tools", default=None)
_active_skill_name: ContextVar[Optional[str]] = ContextVar("active_skill_name", default=None)


def activate_skill_context(*, allowed_tools: Optional[list[str]], skill_name: Optional[str]) -> Token:
    allowed = {item.strip() for item in (allowed_tools or []) if item.strip()} or None
    _active_skill_name.set(skill_name)
    return _skill_allowed_tools.set(allowed)


def deactivate_skill_context(token: Token) -> None:
    _skill_allowed_tools.reset(token)
    _active_skill_name.set(None)


def get_skill_allowed_tools() -> Optional[Set[str]]:
    return _skill_allowed_tools.get()


def get_active_skill_name() -> Optional[str]:
    return _active_skill_name.get()


__all__ = [
    "activate_skill_context",
    "deactivate_skill_context",
    "get_active_skill_name",
    "get_skill_allowed_tools",
]
