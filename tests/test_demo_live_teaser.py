"""Unit tests for allowlisted demo live teaser (weather + FX)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.schemas.content_block import ContentBlock
from app.services.demo_live_teaser import (
    default_demo_intro,
    demo_suggested_prompts,
    detect_demo_live_intent,
    fetch_demo_live_teaser,
)
from app.services.live_tool_result import LiveToolResult


def test_detect_demo_live_intent_weather_variants() -> None:
    assert detect_demo_live_intent("What's the weather in Austin?") == "weather"
    assert detect_demo_live_intent("3-day forecast for Seattle") == "weather"
    assert detect_demo_live_intent("Is it raining in Chicago?") == "weather"
    assert detect_demo_live_intent("temperature in Dallas") == "weather"


def test_detect_demo_live_intent_fx_variants() -> None:
    assert detect_demo_live_intent("USD to INR exchange rate") == "fx"
    assert detect_demo_live_intent("What's the EUR to GBP forex?") == "fx"
    assert detect_demo_live_intent("dollar to rupee") == "fx"
    assert detect_demo_live_intent("currency conversion for CAD") == "fx"


def test_detect_demo_live_intent_non_live_and_empty() -> None:
    assert detect_demo_live_intent("Tell me about his projects") is None
    assert detect_demo_live_intent("How does he play cricket?") is None
    assert detect_demo_live_intent("") is None
    assert detect_demo_live_intent("   ") is None


def test_detect_demo_live_intent_prefers_weather_when_both_match() -> None:
    assert detect_demo_live_intent("weather and USD rate") == "weather"


def test_default_demo_intro_is_honest() -> None:
    intro = default_demo_intro(5)
    assert intro.startswith("Try CurieAI —")
    assert "tool calling" not in intro.lower()
    assert "5 free questions" in intro
    assert "weather" in intro.lower() or "fx" in intro.lower()


def test_demo_suggested_prompts_cover_profile_and_live() -> None:
    prompts = demo_suggested_prompts()
    assert len(prompts) >= 5
    joined = " ".join(prompts).lower()
    assert "sriram" in joined or "academic" in joined or "cricket" in joined
    assert "weather" in joined
    assert "usd" in joined or "exchange" in joined


def test_fetch_demo_live_teaser_skips_non_live_queries() -> None:
    result = asyncio.run(
        fetch_demo_live_teaser(
            query="What has Sriram worked on?",
            live_data=MagicMock(),
            web_search=MagicMock(),
            settings=Settings(),
        )
    )
    assert result.intent is None
    assert result.context == ""
    assert result.blocks == []
    assert result.live is None


def test_fetch_demo_live_teaser_fx_success() -> None:
    block = ContentBlock(
        type="fx",
        data={"source": "frankfurter", "asOf": "2026-07-23T12:00:00Z", "base": "USD", "quote": "INR"},
    )
    with patch("app.services.demo_live_teaser.LiveToolHub") as hub_cls:
        hub = hub_cls.return_value
        hub.get_fx_rate = AsyncMock(
            return_value=LiveToolResult(summary="**USD/INR** — **83.12**", block=block)
        )
        result = asyncio.run(
            fetch_demo_live_teaser(
                query="What's the USD to INR exchange rate?",
                live_data=MagicMock(),
                web_search=MagicMock(),
                settings=Settings(),
            )
        )

    assert result.intent == "fx"
    assert "Fetching live FX" in result.status_message
    assert "Live context" in result.context
    assert "83.12" in result.context
    assert result.blocks[0].type == "fx"
    assert result.live is not None
    assert result.live.source == "frankfurter"
    assert result.live.verified is True


def test_fetch_demo_live_teaser_weather_hub_error_returns_empty_context() -> None:
    with patch("app.services.demo_live_teaser.LiveToolHub") as hub_cls:
        hub = hub_cls.return_value
        hub.get_weather = AsyncMock(side_effect=RuntimeError("upstream down"))
        result = asyncio.run(
            fetch_demo_live_teaser(
                query="weather in Austin",
                live_data=MagicMock(),
                web_search=MagicMock(),
                settings=Settings(),
            )
        )

    assert result.intent == "weather"
    assert result.context == ""
    assert result.blocks == []
    assert result.live is None
    assert "weather" in result.status_message.lower()


def test_fetch_demo_live_teaser_error_summary_skips_context() -> None:
    with patch("app.services.demo_live_teaser.LiveToolHub") as hub_cls:
        hub = hub_cls.return_value
        hub.get_fx_rate = AsyncMock(
            return_value=LiveToolResult(summary="ERROR: FX tool requires a currency pair query", block=None)
        )
        result = asyncio.run(
            fetch_demo_live_teaser(
                query="USD exchange rate",
                live_data=MagicMock(),
                web_search=MagicMock(),
                settings=Settings(),
            )
        )

    assert result.intent == "fx"
    assert result.context == ""
    assert result.blocks == []


def test_fetch_demo_live_teaser_summary_without_block_still_has_provenance() -> None:
    with patch("app.services.demo_live_teaser.LiveToolHub") as hub_cls:
        hub = hub_cls.return_value
        hub.get_weather = AsyncMock(
            return_value=LiveToolResult(summary="Clear skies in Austin, 72F", block=None)
        )
        result = asyncio.run(
            fetch_demo_live_teaser(
                query="weather in Austin",
                live_data=MagicMock(),
                web_search=MagicMock(),
                settings=Settings(),
            )
        )

    assert result.intent == "weather"
    assert "Clear skies" in result.context
    assert result.blocks == []
    assert result.live is not None
    assert result.live.domain == "weather_current"
    assert result.live.source == "live"
