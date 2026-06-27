"""Compose system prompts with sentiment tone and user memory blocks."""

from __future__ import annotations

from typing import Optional

from app.core.config import Settings
from app.services.sentiment_routing import detect_sentiment, tone_instruction_for_sentiment
from app.services.user_memory import UserMemoryStore


def augment_system_prompt(
    base_prompt: str,
    *,
    user_query: str,
    user_id: Optional[str],
    settings: Settings,
    user_memory_store: Optional[UserMemoryStore] = None,
    skill_addendum: Optional[str] = None,
    skill_name: Optional[str] = None,
) -> str:
    parts = [base_prompt.strip()]
    if skill_addendum:
        label = skill_name or "Active skill"
        parts.append(f"## Active skill: {label}\n{skill_addendum.strip()}")
    if settings.enable_sentiment_tone:
        tone = tone_instruction_for_sentiment(detect_sentiment(user_query))
        if tone:
            parts.append(tone)
    if settings.enable_user_memory and user_id and user_memory_store is not None:
        memory_block = user_memory_store.get_memory_block(user_id)
        if memory_block:
            parts.append(memory_block)
    return "\n\n".join(parts)


__all__ = ["augment_system_prompt"]
