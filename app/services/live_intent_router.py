from __future__ import annotations

import re
from typing import Optional

from app.schemas.live_intent import LiveDomain, LiveIntent
from app.services.web_search import (
    detect_commodity_query,
    detect_stock_query,
    extract_currency_pair,
    extract_forecast_days,
    extract_news_topic,
    extract_weather_location,
    is_news_query,
    is_weather_forecast_query,
    is_weather_query,
    should_prioritize_fresh_web_data,
)


def route_live_intent(query: str) -> Optional[LiveIntent]:
    """
    Classify a user query into a live-data domain with structured slots.

    Returns None when the query is not a deterministic live-data intent.
    """
    text = query.strip()
    if not text:
        return None

    pair = extract_currency_pair(text)
    if pair:
        return LiveIntent(
            domain="fx",
            slots={"base": pair[0], "quote": pair[1]},
            confidence=0.98,
        )

    commodity = detect_commodity_query(text)
    if commodity:
        ticker, label = commodity
        return LiveIntent(
            domain="commodity",
            slots={"ticker": ticker, "label": label},
            confidence=0.95,
        )

    ticker = detect_stock_query(text)
    if ticker:
        return LiveIntent(
            domain="stock",
            slots={"ticker": ticker},
            confidence=0.94,
        )

    if is_weather_query(text):
        location = extract_weather_location(text)
        if location:
            if is_weather_forecast_query(text):
                return LiveIntent(
                    domain="weather_forecast",
                    slots={"location": location, "days": extract_forecast_days(text)},
                    confidence=0.92,
                )
            return LiveIntent(
                domain="weather_current",
                slots={"location": location},
                confidence=0.92,
            )

    if is_news_query(text):
        topic = extract_news_topic(text)
        return LiveIntent(
            domain="news",
            slots={"topic": topic},
            confidence=0.9,
        )

    if should_prioritize_fresh_web_data(text):
        return LiveIntent(domain="generic_fresh", slots={}, confidence=0.55)

    return None


def is_structured_live_intent(intent: Optional[LiveIntent]) -> bool:
    """True for adapter-backed domains (excludes generic freshness-only)."""
    return intent is not None and intent.domain != "generic_fresh"


__all__ = ["route_live_intent", "is_structured_live_intent"]
