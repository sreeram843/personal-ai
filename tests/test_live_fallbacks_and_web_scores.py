"""Tests for web evidence scoring and live weather/FX provider fallbacks."""

from __future__ import annotations

import asyncio

import httpx

from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.orchestrated_chat import OrchestratedChatService
from app.services.web_search import WebSearchService


def test_score_web_evidence_prefers_relevant_early_hits() -> None:
    service = OrchestratedChatService(
        embed_client=object(),  # type: ignore[arg-type]
        llm_gateway=object(),  # type: ignore[arg-type]
        model_profile=WorkflowModelProfile(
            planner=StageModelConfig(provider="ollama", model="x"),
            synthesizer=StageModelConfig(provider="ollama", model="x"),
            reviewer=StageModelConfig(provider="ollama", model="x"),
            writer=StageModelConfig(provider="ollama", model="x"),
        ),
        web_search=object(),  # type: ignore[arg-type]
        vector_store=object(),  # type: ignore[arg-type]
        memory_store=object(),  # type: ignore[arg-type]
    )
    query = "kubernetes deployment rollout"
    high = service._score_web_evidence(
        query,
        {"title": "Kubernetes deployment rollout guide", "excerpt": "rollout strategy checklist", "score": 0.9},
        index=1,
    )
    low = service._score_web_evidence(
        query,
        {"title": "Pasta recipes", "excerpt": "tomato sauce tips", "score": 0.1},
        index=5,
    )
    assert high > 0.0
    assert high > low


def test_fx_falls_back_to_open_er_api(monkeypatch) -> None:
    service = WebSearchService(max_results=3, timeout=5.0)
    calls: list[str] = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            calls.append(url)
            if "frankfurter" in url:
                raise httpx.HTTPError("down")
            assert "open.er-api.com" in url
            return _Resp(
                {
                    "result": "success",
                    "base_code": "USD",
                    "rates": {"INR": 83.1},
                    "time_last_update_utc": "Thu, 01 Jan 2026 00:00:00 +0000",
                }
            )

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    result = asyncio.run(service.get_live_fx_rate("USD", "INR"))
    assert result is not None
    assert result["rate"] == 83.1
    assert result["source"] == "open.er-api.com"
    assert any("frankfurter" in url for url in calls)


def test_weather_falls_back_to_wttr(monkeypatch) -> None:
    service = WebSearchService(max_results=3, timeout=5.0)

    async def _no_geo(location: str):
        return None

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "current_condition": [
                    {
                        "temp_C": "22",
                        "FeelsLikeC": "21",
                        "humidity": "40",
                        "precipMM": "0.0",
                        "windspeedKmph": "10",
                        "localObsDateTime": "2026-01-01 12:00 PM",
                    }
                ],
                "nearest_area": [{"areaName": [{"value": "Austin"}]}],
            }

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            assert "wttr.in" in url
            return _Resp()

    monkeypatch.setattr(service, "_geocode_location", _no_geo)
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    result = asyncio.run(service.get_live_weather("Austin"))
    assert result is not None
    assert result["temperature"] == 22.0
    assert result["source"] == "wttr.in"
    assert result["location"] == "Austin"
