"""Structured live intent router tests."""

from __future__ import annotations

from app.services.live_intent_router import is_structured_live_intent, route_live_intent


def test_route_fx_intent_extracts_currency_slots() -> None:
    intent = route_live_intent("usd to inr today")
    assert intent is not None
    assert intent.domain == "fx"
    assert intent.slots["base"] == "USD"
    assert intent.slots["quote"] == "INR"
    assert intent.confidence >= 0.9


def test_route_weather_forecast_before_current() -> None:
    intent = route_live_intent("weather forecast for Austin tomorrow")
    assert intent is not None
    assert intent.domain == "weather_forecast"
    assert intent.slots["location"] == "Austin"
    assert intent.slots["days"] >= 2


def test_route_houston_coming_sunday_uses_forecast_and_city_only() -> None:
    intent = route_live_intent("What is the weather in Houston for coming Sunday?")
    assert intent is not None
    assert intent.domain == "weather_forecast"
    assert intent.slots["location"] == "Houston"
    assert intent.slots["days"] >= 1


def test_generic_freshness_is_not_structured_adapter_intent() -> None:
    intent = route_live_intent("what is happening tomorrow with the product launch")
    assert intent is not None
    assert intent.domain == "generic_fresh"
    assert is_structured_live_intent(intent) is False


def test_stock_intent_extracts_ticker() -> None:
    intent = route_live_intent("stock price of msft")
    assert intent is not None
    assert intent.domain == "stock"
    assert intent.slots["ticker"] == "MSFT"


def test_stock_intent_avoids_false_ticker_from_what_is_stock_price_of() -> None:
    """'What is stock price of TDOC?' must resolve TDOC, not 'IS'."""
    intent = route_live_intent("What is stock price of TDOC?")
    assert intent is not None
    assert intent.domain == "stock"
    assert intent.slots["ticker"] == "TDOC"


def test_stock_intent_prefers_parenthetical_ticker_over_company_name() -> None:
    intent = route_live_intent("What is the current stock price of Apple (AAPL)?")
    assert intent is not None
    assert intent.domain == "stock"
    assert intent.slots["ticker"] == "AAPL"


def test_compare_databases_is_not_soccer_score() -> None:
    intent = route_live_intent(
        "Compare PostgreSQL vs MongoDB for a high-write analytics workload and recommend one."
    )
    assert intent is None or intent.domain != "game_score"


def test_morning_briefing_is_not_single_weather_adapter() -> None:
    intent = route_live_intent(
        "Give me a morning briefing with weather, news, and anything urgent."
    )
    assert intent is None


def test_coffee_shops_seattle_is_nearby_places() -> None:
    intent = route_live_intent("Find good coffee shops near Seattle, WA.")
    assert intent is not None
    assert intent.domain == "nearby_places"
    assert intent.slots["category"] == "coffee"
    assert "Seattle" in str(intent.slots.get("location") or "")

