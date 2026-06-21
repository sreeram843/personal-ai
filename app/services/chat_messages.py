"""Shared chat message helpers (avoids import cycles between runners)."""

from __future__ import annotations

from fastapi import HTTPException

from app.schemas.chat import ChatMessage, ChatRequest


def get_last_user_message(payload: ChatRequest) -> ChatMessage:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="Missing chat messages")

    last_user_message = next((msg for msg in reversed(payload.messages) if msg.role == "user"), None)
    if last_user_message is None:
        raise HTTPException(status_code=400, detail="At least one user message is required")
    return last_user_message


__all__ = ["get_last_user_message"]
