"""Generic freshness (e.g. 'tomorrow') should not hard-fail; adapter-specific intents should."""

from app.services.live_data_manager import LiveDataManager


def test_tomorrow_sports_wording_is_freshness_only() -> None:
    assert LiveDataManager.is_only_generic_freshness_live_intent(
        "Who are playing in tomorrow IPL match?",
    )


def test_weather_query_is_not_freshness_only() -> None:
    assert not LiveDataManager.is_only_generic_freshness_live_intent("weather in Austin tomorrow")


def test_fx_is_not_freshness_only() -> None:
    assert not LiveDataManager.is_only_generic_freshness_live_intent("usd to inr today")


def test_headline_news_is_not_freshness_only() -> None:
    assert not LiveDataManager.is_only_generic_freshness_live_intent("latest headlines on the election")
