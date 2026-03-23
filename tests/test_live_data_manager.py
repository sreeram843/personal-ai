from __future__ import annotations

import asyncio
from typing import Optional

from app.core.config import Settings
from app.schemas.adapter import AdapterResult
from app.services.live_data_manager import LiveDataManager


class _WebStub:
    def __init__(self) -> None:
        self.fx_calls = 0

    async def get_live_fx_rate(self, base: str, quote: str):
        self.fx_calls += 1
        return {
            "base": base,
            "quote": quote,
            "rate": 93.62,
            "date": "2026-03-22",
        }

    async def get_live_commodity_price(self, ticker: str):
        return None

    async def get_live_stock_quote(self, ticker: str):
        return None

    async def get_live_weather(self, location: str):
        return None

    async def get_live_weather_forecast(self, location: str, days: int = 3):
        return None

    async def get_live_news(self, topic: str, limit: int = 5):
        return None


class _TestCache:
    def __init__(self) -> None:
        self._store: dict[str, AdapterResult] = {}

    async def get(self, key: str) -> Optional[AdapterResult]:
        return self._store.get(key)

    async def set(self, key: str, value: AdapterResult, ttl_seconds: int) -> None:
        self._store[key] = value


def test_live_data_manager_fx_resolution_uses_cache() -> None:
    """Repeated FX requests should return from cache and avoid duplicate provider calls."""
    web = _WebStub()
    manager = LiveDataManager(web_search=web, cache=_TestCache(), settings=Settings())

    first = asyncio.run(manager.resolve("usd to inr"))
    second = asyncio.run(manager.resolve("usd to inr"))

    assert first is not None
    assert first.status == "ok"
    assert first.verified is True
    assert second is not None
    assert second.data == first.data
    assert web.fx_calls == 1


def test_is_live_intent_query_detects_supported_domains() -> None:
    web = _WebStub()
    manager = LiveDataManager(web_search=web, cache=_TestCache(), settings=Settings())

    assert manager.is_live_intent_query("usd to inr") is True
    assert manager.is_live_intent_query("price of gold right now") is True
    assert manager.is_live_intent_query("stock price of msft") is True
    assert manager.is_live_intent_query("weather in austin") is True
    assert manager.is_live_intent_query("latest ai news") is True
    assert manager.is_live_intent_query("explain recursion with an example") is False


def test_unresolved_live_intent_render_is_deterministic() -> None:
    web = _WebStub()
    manager = LiveDataManager(web_search=web, cache=_TestCache(), settings=Settings())

    result = manager.unresolved_live_intent_result()
    msg, fetched = manager.render(result)

    assert result.status == "error"
    assert result.error_code == "LIVE_DATA_NOT_VERIFIED"
    assert "ERROR 404: LIVE DATA NOT VERIFIED" in msg
    assert "Source: Live Adapter Router" in msg
    assert fetched == result.fetched_at_utc


def test_render_news_response_includes_provider_metadata() -> None:
    web = _WebStub()
    manager = LiveDataManager(web_search=web, cache=_TestCache(), settings=Settings())

    result = AdapterResult(
        domain="news",
        status="ok",
        verified=True,
        source="Google News RSS",
        provider_timestamp="2026-03-22T23:59:00Z",
        fetched_at_utc="2026-03-23 00:00:01 UTC",
        ttl_seconds=180,
        data={
            "topic": "ai",
            "headlines": [
                {
                    "title": "AI headline",
                    "source": "Example News",
                    "published_at": "2026-03-22T23:59:00Z",
                    "link": "https://example.com/story",
                }
            ],
        },
    )

    message, fetched = manager.render(result)

    assert "LIVE NEWS DATA RETRIEVED" in message
    assert "AI headline" in message
    assert "link=https://example.com/story" in message
    assert "Source: Google News RSS" in message
    assert fetched == "2026-03-23 00:00:01 UTC"
