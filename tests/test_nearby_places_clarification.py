"""Tests for nearby places LLM clarification gate."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.schemas.live_intent import LiveIntent
from app.services.llm_gateway import StageModelConfig
from app.services.nearby_places_clarification import (
    assess_nearby_places_readiness,
    heuristic_assess_nearby_places,
    should_use_llm_clarification,
)


def _intent(**slots: object) -> LiveIntent:
    return LiveIntent(domain="nearby_places", slots=dict(slots), confidence=0.9)


def test_heuristic_near_me_asks_location_without_llm() -> None:
    intent = _intent(category="food", location="", needs_location=True)
    assessment = heuristic_assess_nearby_places("restaurants near me", intent)
    assert assessment.ready_to_search is False
    assert "city or neighborhood" in assessment.question.lower()


def test_heuristic_clear_query_is_ready() -> None:
    intent = _intent(category="coffee", location="Portland, Oregon", needs_location=False)
    assessment = heuristic_assess_nearby_places("coffee shops in Portland, Oregon", intent)
    assert assessment.ready_to_search is True
    assert assessment.location == "Portland, Oregon"


def test_should_use_llm_for_vague_landmark() -> None:
    intent = _intent(category="food", location="the stadium", needs_location=False)
    assert should_use_llm_clarification("restaurants near the stadium", intent) is True


@pytest.mark.asyncio
async def test_assess_uses_llm_for_ambiguous_query() -> None:
    intent = _intent(category="food", location="the stadium", needs_location=False)
    gateway = MagicMock()
    gateway.generate = AsyncMock(
        return_value=(
            '{"ready_to_search": false, "location": "", "category": "food", '
            '"question": "Which stadium and city should I search near?"}'
        )
    )
    settings = Settings(enable_nearby_places_llm_clarification=True)
    planner = StageModelConfig(provider="ollama", model="qwen2.5:3b")

    assessment = await assess_nearby_places_readiness(
        "nice dinner near the stadium",
        intent,
        chat_history=[],
        settings=settings,
        llm_gateway=gateway,
        planner=planner,
    )

    assert assessment.ready_to_search is False
    assert "stadium" in assessment.question.lower()
    gateway.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_assess_skips_llm_when_disabled() -> None:
    intent = _intent(category="food", location="the stadium", needs_location=False)
    gateway = MagicMock()
    gateway.generate = AsyncMock()
    settings = Settings(enable_nearby_places_llm_clarification=False)

    assessment = await assess_nearby_places_readiness(
        "nice dinner near the stadium",
        intent,
        chat_history=[],
        settings=settings,
        llm_gateway=gateway,
        planner=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
    )

    assert assessment.ready_to_search is True
    assert assessment.location == "the stadium"
    gateway.generate.assert_not_called()


@pytest.mark.asyncio
async def test_assess_near_me_never_calls_llm() -> None:
    intent = _intent(category="food", location="", needs_location=True)
    gateway = MagicMock()
    gateway.generate = AsyncMock()
    settings = Settings(enable_nearby_places_llm_clarification=True)

    assessment = await assess_nearby_places_readiness(
        "restaurants near me",
        intent,
        chat_history=[],
        settings=settings,
        llm_gateway=gateway,
        planner=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
    )

    assert assessment.ready_to_search is False
    gateway.generate.assert_not_called()
