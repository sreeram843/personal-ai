"""Tool-routing golden set adapted from BFCL-style cases (builtin_tools surface)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.information_routing import is_document_grounded_query
from app.services.live_intent_router import route_live_intent

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tool_calling_golden.json"
GOLDEN_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))

DOMAIN_TO_TOOL = {
    "fx": "fx_rate",
    "stock": "market_price",
    "commodity": "market_price",
    "weather_current": "weather",
    "weather_forecast": "weather_forecast",
    "news": "news",
    "generic_fresh": "web_search",
}


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case["id"])
def test_tool_calling_golden_fixture(case: dict) -> None:
    expected_tool = case["expected_tool_id"]
    if expected_tool == "search_documents":
        assert is_document_grounded_query(case["query"]) is True
        return

    intent = route_live_intent(case["query"])
    assert intent is not None, f"No live intent for: {case['query']}"
    assert intent.domain == case["expected_domain"]
    assert DOMAIN_TO_TOOL[intent.domain] == expected_tool
