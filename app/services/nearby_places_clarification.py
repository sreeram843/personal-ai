"""LLM-assisted clarification gate for ambiguous nearby-places queries."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, Sequence

from app.core.config import Settings
from app.schemas.live_intent import LiveIntent
from app.services.llm_gateway import LLMGateway, StageModelConfig
from app.services.local_places import (
    extract_nearby_category,
    location_prompt_text,
)

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """You decide whether a nearby-places search can run now or needs one user clarification.
Return JSON only:
{
  "ready_to_search": true|false,
  "location": "city/neighborhood or empty",
  "category": "food|coffee|bar|things_to_do|hotel|general",
  "question": "one short clarifying question or empty string"
}

Rules:
- ready_to_search=true only when location is specific enough to geocode (city, neighborhood, or 'City, ST').
- If the user said near me / nearby / around me and no area is given, ready_to_search=false and ask for city/neighborhood.
- If location is vague (e.g. 'the stadium', 'downtown' without a city), ask which city or which landmark.
- Ask at most ONE question. Prefer the highest-impact missing detail (usually location).
- Do not invent a location the user did not provide.
- category: infer from the user message; use general when unclear."""

_VAGUE_LOCATION_MARKERS: tuple[str, ...] = (
    "the stadium",
    "the arena",
    "the airport",
    "the convention center",
    "that area",
    "around here",
    "this area",
    "over there",
    "near here",
)

_AMBIGUITY_MARKERS: tuple[str, ...] = (
    "somewhere",
    "a good",
    "nice place",
    "kid friendly",
    "family friendly",
    "romantic",
    "quiet spot",
    "cheap",
    "upscale",
    "fancy",
    "best spot",
)

_VALID_CATEGORIES = frozenset({"food", "coffee", "bar", "things_to_do", "hotel", "general"})


@dataclass(frozen=True)
class NearbyPlacesAssessment:
    ready_to_search: bool
    location: str = ""
    category: str = "general"
    question: str = ""


def should_use_llm_clarification(query: str, intent: LiveIntent) -> bool:
    """True when heuristics are not enough and the planner should judge ambiguity."""
    if bool(intent.slots.get("needs_location")):
        return False

    location = str(intent.slots.get("location") or "").strip()
    lowered = query.lower()

    if not location:
        return True
    if any(marker in lowered for marker in _AMBIGUITY_MARKERS):
        return True
    if any(marker in lowered for marker in _VAGUE_LOCATION_MARKERS):
        return True
    if len(location.split()) <= 2 and "," not in location:
        vague_tokens = {"downtown", "uptown", "midtown", "here", "there", "nearby"}
        if any(token in location.lower().split() for token in vague_tokens):
            return True
    return False


def heuristic_assess_nearby_places(query: str, intent: LiveIntent) -> NearbyPlacesAssessment:
    """Fast path before any LLM call."""
    category = str(intent.slots.get("category") or extract_nearby_category(query))
    location = str(intent.slots.get("location") or "").strip()
    needs_location = bool(intent.slots.get("needs_location")) or not location

    if needs_location:
        return NearbyPlacesAssessment(
            ready_to_search=False,
            category=category,
            question=location_prompt_text(category=category),
        )

    if location and not should_use_llm_clarification(query, intent):
        return NearbyPlacesAssessment(
            ready_to_search=True,
            location=location,
            category=category,
        )

    return NearbyPlacesAssessment(
        ready_to_search=False,
        location=location,
        category=category,
        question="",
    )


def _format_history(chat_history: Sequence[dict[str, str]], *, max_turns: int = 4) -> str:
    lines: list[str] = []
    for message in chat_history[-max_turns:]:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(no prior turns)"


def _normalize_category(value: str) -> str:
    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in _VALID_CATEGORIES:
        return cleaned
    return "general"


def _parse_assessment(raw: str) -> Optional[NearbyPlacesAssessment]:
    candidate = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate, flags=re.IGNORECASE)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        object_match = re.search(r"(\{[\s\S]*\})", candidate)
        if object_match:
            candidate = object_match.group(1)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    ready = bool(payload.get("ready_to_search"))
    location = str(payload.get("location") or "").strip()
    category = _normalize_category(str(payload.get("category") or "general"))
    question = str(payload.get("question") or "").strip()

    if ready and not location:
        ready = False
        if not question:
            question = location_prompt_text(category=category)

    return NearbyPlacesAssessment(
        ready_to_search=ready,
        location=location,
        category=category,
        question=question,
    )


async def llm_assess_nearby_places(
    query: str,
    intent: LiveIntent,
    *,
    chat_history: Sequence[dict[str, str]] | None,
    settings: Settings,
    llm_gateway: LLMGateway,
    planner: StageModelConfig,
) -> Optional[NearbyPlacesAssessment]:
    history_text = _format_history(chat_history or ())
    heuristic = heuristic_assess_nearby_places(query, intent)
    response = await llm_gateway.generate(
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"User message:\n{query}\n\n"
                    f"Parsed slots:\n"
                    f"- location: {intent.slots.get('location') or ''}\n"
                    f"- category: {intent.slots.get('category') or 'general'}\n"
                    f"- needs_location: {bool(intent.slots.get('needs_location'))}\n\n"
                    f"Recent conversation:\n{history_text}\n\n"
                    f"Heuristic guess: ready={heuristic.ready_to_search}, "
                    f"location={heuristic.location!r}, category={heuristic.category!r}"
                ),
            },
        ],
        model=planner.model,
        provider=planner.provider,
        options={"temperature": 0.0},
    )
    return _parse_assessment(response)


async def assess_nearby_places_readiness(
    query: str,
    intent: LiveIntent,
    *,
    chat_history: Sequence[dict[str, str]] | None,
    settings: Settings,
    llm_gateway: LLMGateway | None = None,
    planner: StageModelConfig | None = None,
) -> NearbyPlacesAssessment:
    """
    Hybrid clarification gate: deterministic rules first, planner model for ambiguous cases.
    """
    heuristic = heuristic_assess_nearby_places(query, intent)
    if heuristic.ready_to_search or heuristic.question:
        return heuristic

    if (
        not settings.enable_nearby_places_llm_clarification
        or llm_gateway is None
        or planner is None
        or not should_use_llm_clarification(query, intent)
    ):
        if heuristic.location:
            return NearbyPlacesAssessment(
                ready_to_search=True,
                location=heuristic.location,
                category=heuristic.category,
            )
        return NearbyPlacesAssessment(
            ready_to_search=False,
            category=heuristic.category,
            question=location_prompt_text(category=heuristic.category),
        )

    try:
        llm_result = await llm_assess_nearby_places(
            query,
            intent,
            chat_history=chat_history,
            settings=settings,
            llm_gateway=llm_gateway,
            planner=planner,
        )
    except Exception:
        logger.exception("Nearby places LLM clarification failed; using heuristic fallback")
        llm_result = None

    if llm_result is None:
        if heuristic.location:
            return NearbyPlacesAssessment(
                ready_to_search=True,
                location=heuristic.location,
                category=heuristic.category,
            )
        return NearbyPlacesAssessment(
            ready_to_search=False,
            category=heuristic.category,
            question=location_prompt_text(category=heuristic.category),
        )

    if llm_result.ready_to_search:
        return llm_result

    question = llm_result.question.strip() or location_prompt_text(category=llm_result.category)
    return NearbyPlacesAssessment(
        ready_to_search=False,
        location=llm_result.location,
        category=llm_result.category,
        question=question,
    )


__all__ = [
    "NearbyPlacesAssessment",
    "assess_nearby_places_readiness",
    "heuristic_assess_nearby_places",
    "should_use_llm_clarification",
]
