"""Tests for nearby places detection and follow-up handling."""

from __future__ import annotations

import pytest

from app.services.information_routing import is_external_web_lookup_query, prefers_tool_agent_for_query
from app.services.live_intent_router import route_live_intent
from app.services.local_places import (
    detect_nearby_places_follow_up,
    extract_nearby_category,
    extract_nearby_location,
    is_nearby_places_query,
    location_prompt_text,
    looks_like_location_reply,
)


@pytest.mark.parametrize(
    "query, expected",
    [
        ("restaurants near me", True),
        ("coffee nearby", True),
        ("things to do in Austin", True),
        ("best pizza near downtown Seattle", True),
        ("weather in Austin", False),
        ("NVDA stock price", False),
    ],
)
def test_is_nearby_places_query(query: str, expected: bool) -> None:
    assert is_nearby_places_query(query) is expected


def test_extract_nearby_location_and_category() -> None:
    assert extract_nearby_location("best restaurants in Austin, TX") == "Austin, TX"
    assert extract_nearby_location("coffee near me") is None
    assert extract_nearby_category("coffee shops near me") == "coffee"
    assert extract_nearby_category("things to do in Denver") == "things_to_do"


def test_route_nearby_places_without_location() -> None:
    intent = route_live_intent("restaurants near me")
    assert intent is not None
    assert intent.domain == "nearby_places"
    assert intent.slots["needs_location"] is True
    assert intent.slots["category"] == "food"


def test_route_nearby_places_with_location() -> None:
    intent = route_live_intent("coffee shops in Portland, Oregon")
    assert intent is not None
    assert intent.domain == "nearby_places"
    assert intent.slots["location"] == "Portland, Oregon"
    assert intent.slots["needs_location"] is False


def test_location_follow_up_from_chat_history() -> None:
    history = [
        {"role": "user", "content": "food near me"},
        {
            "role": "assistant",
            "content": location_prompt_text(category="food"),
        },
    ]
    assert looks_like_location_reply("Austin, TX") is True
    follow_up = detect_nearby_places_follow_up("Austin, TX", history)
    assert follow_up == {"location": "Austin, TX", "category": "food"}
    intent = route_live_intent("Austin, TX", chat_history=history)
    assert intent is not None
    assert intent.domain == "nearby_places"
    assert intent.slots["location"] == "Austin, TX"


def test_near_me_routes_to_tool_agent() -> None:
    query = "restaurants near me"
    assert is_external_web_lookup_query(query) is True
    assert prefers_tool_agent_for_query(query) is True
