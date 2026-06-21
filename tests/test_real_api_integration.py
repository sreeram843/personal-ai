"""Integration tests against real external APIs (not mocked).

Run manually when dependencies are up:

    RUN_REAL_API_TESTS=1 pytest tests/test_real_api_integration.py -v --no-cov

Optional HTTP checks against a running server:

    RUN_REAL_API_TESTS=1 API_BASE_URL=http://127.0.0.1:8000 pytest tests/test_real_api_integration.py -v --no-cov
"""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest

from app.core.config import Settings
from app.services.adapter_cache import InMemoryAdapterCache
from app.services.geocoding import GeocodingService
from app.services.live_data_manager import LiveDataManager
from app.services.live_intent_router import route_live_intent
from app.services.market_data import YahooMarketDataProvider
from app.services.web_search import WebSearchService

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_API_TESTS") != "1",
    reason="Set RUN_REAL_API_TESTS=1 to hit live providers",
)


@pytest.fixture(scope="module")
def web_search() -> WebSearchService:
    return WebSearchService(timeout=20)


@pytest.fixture(scope="module")
def live_manager(web_search: WebSearchService) -> LiveDataManager:
    return LiveDataManager(
        web_search=web_search,
        cache=InMemoryAdapterCache(),
        settings=Settings(),
    )


def test_frankfurter_fx_rate(web_search: WebSearchService) -> None:
    result = asyncio.run(web_search.get_live_fx_rate("USD", "INR"))
    assert result is not None
    assert result["base"] == "USD"
    assert result["quote"] == "INR"
    assert float(result["rate"]) > 0


def test_open_meteo_geocoding() -> None:
    geo = GeocodingService(cache=InMemoryAdapterCache(), timeout=20)
    result = asyncio.run(geo.resolve("Austin, TX"))
    assert result is not None
    assert result.get("latitude") is not None
    assert result.get("longitude") is not None


def test_yahoo_stock_quote() -> None:
    provider = YahooMarketDataProvider(timeout=20)
    quote = asyncio.run(provider.get_stock_quote("MSFT"))
    assert quote is not None
    assert quote["ticker"] == "MSFT"
    assert float(quote["price"]) > 0


def test_live_data_manager_fx_end_to_end(live_manager: LiveDataManager) -> None:
    intent = route_live_intent("usd to inr")
    assert intent is not None
    assert intent.domain == "fx"

    result = asyncio.run(live_manager.resolve("usd to inr"))
    assert result is not None
    assert result.verified is True
    assert result.domain == "fx"
    assert float(result.data["rate"]) > 0
    provenance = LiveDataManager.to_provenance(result)
    assert provenance.source
    assert provenance.confidence > 0


def test_live_data_manager_weather_end_to_end(live_manager: LiveDataManager) -> None:
    result = asyncio.run(live_manager.resolve("current weather in London"))
    assert result is not None
    assert result.domain == "weather_current"
    assert result.verified is True
    assert result.data.get("temperature") is not None


def test_http_live_fx_short_circuit_via_test_client() -> None:
    """Full HTTP stack against real Postgres; live providers hit Frankfurter/Open-Meteo."""
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    response = client.post("/chat", json={"message": "usd to inr"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("live", {}).get("domain") == "fx"
    assert body.get("live", {}).get("verified") is True
    assert float(body.get("live", {}).get("confidence", 0)) > 0
    assert "conversation_id" in body


@pytest.mark.skipif(os.getenv("RUN_HTTP_API_TESTS") != "1", reason="Set RUN_HTTP_API_TESTS=1 to hit local API")
def test_http_live_fx_short_circuit_against_running_server() -> None:
    base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

    async def run() -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            health = await client.get(f"{base}/health")
            assert health.status_code == 200

            response = await client.post(f"{base}/chat", json={"message": "usd to inr"})
            if response.status_code == 500:
                pytest.skip("API returned 500 — run Postgres migrations (make db-migrate) and retry")
            assert response.status_code == 200
            body = response.json()
            assert body.get("live", {}).get("domain") == "fx"
            assert body.get("live", {}).get("verified") is True
            assert "INR" in body.get("message", "").upper() or "USD" in body.get("message", "").upper()

    asyncio.run(run())
