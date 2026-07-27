from __future__ import annotations

import re
from typing import Optional, Sequence

from app.schemas.live_intent import LiveDomain, LiveIntent
from app.services.live_sports import SportsGameQuery, detect_sports_game_query
from app.services.local_places import (
    detect_nearby_places_follow_up,
    extract_nearby_category,
    extract_nearby_location,
    is_nearby_places_query,
)
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


def route_live_intent(
    query: str,
    *,
    chat_history: Sequence[dict[str, str]] | None = None,
) -> Optional[LiveIntent]:
    """
    Classify a user query into a live-data domain with structured slots.

    Returns None when the query is not a deterministic live-data intent.
    """
    text = query.strip()
    if not text:
        return None

    # Compound briefings (weather + news, etc.) belong to the orchestrator —
    # a single adapter short-circuit produces bad locations / incomplete answers.
    if _is_compound_live_request(text):
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

    follow_up = detect_nearby_places_follow_up(text, chat_history or ())
    if follow_up:
        return LiveIntent(
            domain="nearby_places",
            slots=follow_up,
            confidence=0.9,
        )

    if is_nearby_places_query(text):
        category = extract_nearby_category(text)
        location = extract_nearby_location(text)
        return LiveIntent(
            domain="nearby_places",
            slots={
                "category": category,
                "location": location or "",
                "needs_location": not bool(location),
            },
            confidence=0.9 if location else 0.85,
        )

    sports = detect_sports_game_query(text)
    if sports:
        return LiveIntent(
            domain="game_score",
            slots={
                "league": sports.league,
                "team_query": sports.team_query,
                "opponent_query": sports.opponent_query or "",
            },
            confidence=0.9,
        )

    if should_prioritize_fresh_web_data(text):
        return LiveIntent(domain="generic_fresh", slots={}, confidence=0.55)

    return None


def _is_compound_live_request(text: str) -> bool:
    """True when the user asks for multiple live domains in one turn (e.g. morning briefing)."""
    lowered = text.lower()
    if re.search(r"\b(briefing|morning update|daily update|digest)\b", lowered):
        return True

    # Long multi-section / meta prompts often embed example live queries
    # ("Extract the ticker from: … Apple (AAPL)"). Those must not short-circuit
    # to a single stock/weather adapter.
    if text.count("###") >= 2 or text.count("## ") >= 3:
        return True
    if len(text.split()) >= 120:
        return True
    if re.search(
        r"extract the ticker from|required output format|capability matrix|"
        r"stress-test|self-critique|evaluate a multi-provider",
        lowered,
    ):
        return True

    signals = 0
    if is_weather_query(text):
        signals += 1
    if is_news_query(text):
        signals += 1
    if detect_stock_query(text) is not None or detect_commodity_query(text) is not None:
        signals += 1
    if is_nearby_places_query(text):
        signals += 1
    if extract_currency_pair(text):
        signals += 1
    return signals >= 2


def is_structured_live_intent(intent: Optional[LiveIntent]) -> bool:
    """True for adapter-backed domains (excludes generic freshness-only)."""
    return intent is not None and intent.domain != "generic_fresh"


__all__ = ["route_live_intent", "is_structured_live_intent"]
