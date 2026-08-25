"""Resolve which skill/assistant is active for an agent run."""

from __future__ import annotations

from typing import Any, Optional

from app.schemas.chat import ChatRequest
from app.services.skill_loader import ResolvedSkill, SkillCatalog


def assistant_id_from_options(options: Optional[dict[str, Any]]) -> Optional[str]:
    raw = (options or {}).get("assistant_id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def resolve_active_skill(
    catalog: SkillCatalog,
    *,
    user_id: str,
    query: str,
    assistant_id: Optional[str] = None,
) -> Optional[ResolvedSkill]:
    """Prefer an explicit assistant on the conversation; otherwise match triggers."""
    if assistant_id:
        skill = catalog.get_by_id(user_id, assistant_id)
        if skill is not None and skill.enabled:
            return ResolvedSkill(skill=skill, matched_by="assistant")
        return None
    resolved = catalog.resolve(query, user_id=user_id)
    if resolved is not None:
        catalog.record_implicit_use(user_id, resolved.skill.id)
    return resolved


def resolve_skill_for_request(
    catalog: SkillCatalog,
    *,
    user_id: str,
    payload: ChatRequest,
    conversation_assistant_id: Optional[str] = None,
) -> Optional[ResolvedSkill]:
    explicit = assistant_id_from_options(payload.options) or conversation_assistant_id
    query = payload.messages[-1].content if payload.messages else ""
    return resolve_active_skill(
        catalog,
        user_id=user_id,
        query=query,
        assistant_id=explicit,
    )


__all__ = [
    "assistant_id_from_options",
    "resolve_active_skill",
    "resolve_skill_for_request",
]
