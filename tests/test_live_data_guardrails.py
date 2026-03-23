from __future__ import annotations

from typing import Optional

from fastapi.testclient import TestClient

from app.core.deps import get_live_data_manager
from app.main import app
from app.schemas.adapter import AdapterResult


class _StubLiveDataManager:
    def __init__(self, resolve_result: Optional[AdapterResult], live_intent: bool = False):
        self._resolve_result = resolve_result
        self._live_intent = live_intent

    async def resolve(self, query: str) -> Optional[AdapterResult]:
        return self._resolve_result

    def is_live_intent_query(self, query: str) -> bool:
        return self._live_intent

    def unresolved_live_intent_result(self) -> AdapterResult:
        return AdapterResult(
            domain="live_query",
            status="error",
            verified=False,
            source="Live Adapter Router",
            fetched_at_utc="2026-03-22 23:59:59 UTC",
            ttl_seconds=10,
            error_code="LIVE_DATA_NOT_VERIFIED",
            error_message="No adapter produced verifiable live data",
        )

    def render(self, result: AdapterResult) -> tuple[str, str]:
        if result.status == "ok" and result.verified:
            return (
                "LIVE DATA RETRIEVED.\n"
                f"- Source: {result.source}\n"
                f"- Fetched: {result.fetched_at_utc}",
                result.fetched_at_utc,
            )
        return (
            "LIVE QUERY DATA REQUEST RECEIVED.\n"
            "ERROR 404: LIVE DATA NOT VERIFIED\n"
            f"- Source: {result.source}\n"
            f"- Fetched: {result.fetched_at_utc}",
            result.fetched_at_utc,
        )


def test_chat_returns_deterministic_adapter_response_with_provenance() -> None:
    """Live adapter success should short-circuit with source and fetch timestamps."""
    stub = _StubLiveDataManager(
        resolve_result=AdapterResult(
            domain="fx",
            status="ok",
            verified=True,
            source="Frankfurter API",
            fetched_at_utc="2026-03-22 23:58:00 UTC",
            ttl_seconds=60,
            data={"base": "USD", "quote": "INR", "rate": 93.62},
        ),
    )
    app.dependency_overrides[get_live_data_manager] = lambda: stub

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "usd to inr value"})
        assert response.status_code == 200
        payload = response.json()
        message = payload["message"]
        assert "LIVE DATA RETRIEVED" in message
        assert "Source: Frankfurter API" in message
        assert "Fetched: 2026-03-22 23:58:00 UTC" in message
        assert "Data fetched: 2026-03-22 23:58:00 UTC" in message
    finally:
        app.dependency_overrides.clear()


def test_rag_chat_returns_deterministic_adapter_response_with_provenance() -> None:
    """RAG route should also short-circuit to verified live data with provenance markers."""
    stub = _StubLiveDataManager(
        resolve_result=AdapterResult(
            domain="weather_current",
            status="ok",
            verified=True,
            source="Open-Meteo",
            fetched_at_utc="2026-03-22 23:58:00 UTC",
            ttl_seconds=300,
            data={"location": "Austin", "temperature": 22},
        ),
    )
    app.dependency_overrides[get_live_data_manager] = lambda: stub

    try:
        client = TestClient(app)
        response = client.post("/rag_chat", json={"message": "weather in austin"})
        assert response.status_code == 200
        payload = response.json()
        message = payload["message"]
        assert "LIVE DATA RETRIEVED" in message
        assert "Source: Open-Meteo" in message
        assert "Fetched: 2026-03-22 23:58:00 UTC" in message
        assert "Data fetched: 2026-03-22 23:58:00 UTC" in message
        assert payload["sources"] == []
    finally:
        app.dependency_overrides.clear()


def test_chat_live_intent_unresolved_returns_guardrail_error() -> None:
    """Live intent with no verified adapter data must never fall through to free-form generation."""
    stub = _StubLiveDataManager(resolve_result=None, live_intent=True)
    app.dependency_overrides[get_live_data_manager] = lambda: stub

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "weather in unknowncityxyz"})
        assert response.status_code == 200
        payload = response.json()
        message = payload["message"]
        assert "ERROR 404: LIVE DATA NOT VERIFIED" in message
        assert "Source: Live Adapter Router" in message
        assert "Data fetched: 2026-03-22 23:59:59 UTC" in message
    finally:
        app.dependency_overrides.clear()


def test_rag_chat_live_intent_unresolved_returns_guardrail_error() -> None:
    """RAG route should enforce the same live-intent deterministic guardrail."""
    stub = _StubLiveDataManager(resolve_result=None, live_intent=True)
    app.dependency_overrides[get_live_data_manager] = lambda: stub

    try:
        client = TestClient(app)
        response = client.post("/rag_chat", json={"message": "weather in unknowncityxyz"})
        assert response.status_code == 200
        payload = response.json()
        message = payload["message"]
        assert "ERROR 404: LIVE DATA NOT VERIFIED" in message
        assert "Source: Live Adapter Router" in message
        assert "Data fetched: 2026-03-22 23:59:59 UTC" in message
    finally:
        app.dependency_overrides.clear()


def test_metrics_endpoint_exposed() -> None:
    """Prometheus endpoint should be available for scraping."""
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "python_gc_objects_collected_total" in response.text
