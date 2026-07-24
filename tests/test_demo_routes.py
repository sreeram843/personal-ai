"""Tests for public portfolio demo API."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.schemas.chat import ChatResponse
from app.schemas.content_block import ContentBlock
from app.schemas.live_intent import LiveDataProvenance
from app.services.demo_live_teaser import DemoLiveTeaserResult
from tests.conftest import apply_db_auth_overrides


@pytest.fixture
def demo_client(db_session) -> TestClient:
    app = create_app()
    settings = apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: Settings(
        **{
            **settings.model_dump(),
            "demo_enabled": True,
            "demo_max_questions": 2,
            "demo_full_app_url": "https://app.cura-i.com",
        }
    )
    return TestClient(app)


def _parse_sse_events(raw: str) -> list[dict]:
    events: list[dict] = []
    for frame in raw.split("\n\n"):
        lines = [line for line in frame.split("\n") if line.startswith("data:")]
        if not lines:
            continue
        payload = "\n".join(line[5:].strip() for line in lines)
        if payload:
            events.append(json.loads(payload))
    return events


def test_demo_config_disabled_by_default(client: TestClient) -> None:
    response = client.get("/demo/config")
    assert response.status_code == 404


def test_demo_config_when_enabled(demo_client: TestClient) -> None:
    response = demo_client.get("/demo/config")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["max_questions"] == 2
    assert "intro" in body
    assert "live data and tool calling" not in body["intro"].lower()
    assert body["full_app_url"] == "https://app.cura-i.com"
    assert isinstance(body["suggested_prompts"], list)
    assert len(body["suggested_prompts"]) >= 4
    assert any("weather" in p.lower() for p in body["suggested_prompts"])
    assert any("usd" in p.lower() or "exchange" in p.lower() for p in body["suggested_prompts"])


def test_demo_config_custom_intro(db_session) -> None:
    app = create_app()
    settings = apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: Settings(
        **{
            **settings.model_dump(),
            "demo_enabled": True,
            "demo_intro": "Custom portfolio intro for visitors.",
            "demo_full_app_url": "https://app.cura-i.com",
        }
    )
    client = TestClient(app)
    body = client.get("/demo/config").json()
    assert body["intro"] == "Custom portfolio intro for visitors."


def test_demo_chat_increments_quota(demo_client: TestClient) -> None:
    fake_response = ChatResponse(message="Hello from demo", sources=[], workflow=None)

    with patch("app.api.demo_routes.run_fast_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=DemoLiveTeaserResult(),
        ):
            first = demo_client.post(
                "/demo/chat",
                json={"session_id": "demo-session-1", "message": "Hi", "messages": []},
            )
            second = demo_client.post(
                "/demo/chat",
                json={"session_id": "demo-session-1", "message": "Again", "messages": []},
            )
            third = demo_client.post(
                "/demo/chat",
                json={"session_id": "demo-session-1", "message": "Too many", "messages": []},
            )

    assert first.status_code == 200
    assert first.json()["questions_used"] == 1
    assert first.json()["questions_remaining"] == 1
    assert first.json()["full_app_url"] == "https://app.cura-i.com"

    assert second.status_code == 200
    assert second.json()["limit_reached"] is True

    assert third.status_code == 429


def test_demo_chat_injects_live_teaser(demo_client: TestClient) -> None:
    fake_response = ChatResponse(message="Austin is clear and 72F.", sources=[], workflow=None)
    block = ContentBlock(type="weather", data={"source": "open-meteo", "asOf": "2026-07-23T18:00:00Z"})
    teaser = DemoLiveTeaserResult(
        intent="weather",
        context="## Live context\nClear skies",
        blocks=[block],
        live=LiveDataProvenance(
            domain="weather",
            source="open-meteo",
            fetched_at_utc="2026-07-23T18:00:00Z",
        ),
        status_message="Fetching live weather…",
    )

    with patch("app.api.demo_routes.run_fast_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=teaser,
        ):
            response = demo_client.post(
                "/demo/chat",
                json={
                    "session_id": "demo-session-live",
                    "message": "What's the weather in Austin?",
                    "messages": [],
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Austin is clear and 72F."
    assert len(body["blocks"]) == 1
    assert body["blocks"][0]["type"] == "weather"
    assert body["live"]["source"] == "open-meteo"
    assert mock_chat.await_args.kwargs["system_prompt"]
    assert "Live context" in mock_chat.await_args.kwargs["system_prompt"]


def test_demo_chat_fx_teaser_returns_blocks(demo_client: TestClient) -> None:
    fake_response = ChatResponse(message="USD/INR is about 83.", sources=[], workflow=None)
    block = ContentBlock(type="fx", data={"source": "frankfurter", "asOf": "now"})
    teaser = DemoLiveTeaserResult(
        intent="fx",
        context="## Live context\nUSD/INR 83.1",
        blocks=[block],
        status_message="Fetching live FX rate…",
    )

    with patch("app.api.demo_routes.run_fast_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=teaser,
        ):
            response = demo_client.post(
                "/demo/chat",
                json={
                    "session_id": "demo-session-fx",
                    "message": "What's the USD to INR exchange rate?",
                    "messages": [],
                },
            )

    assert response.status_code == 200
    assert response.json()["blocks"][0]["type"] == "fx"
    assert "Live context" in mock_chat.await_args.kwargs["system_prompt"]


def test_demo_chat_llm_failure_returns_502(demo_client: TestClient) -> None:
    with patch(
        "app.api.demo_routes.run_fast_chat",
        new_callable=AsyncMock,
        side_effect=RuntimeError("model down"),
    ):
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=DemoLiveTeaserResult(),
        ):
            response = demo_client.post(
                "/demo/chat",
                json={"session_id": "demo-session-fail", "message": "Hi", "messages": []},
            )

    assert response.status_code == 502
    assert "Demo chat failed" in response.json()["detail"]


def test_demo_chat_provider_rate_limit_returns_friendly_429(demo_client: TestClient) -> None:
    with patch(
        "app.api.demo_routes.run_fast_chat",
        new_callable=AsyncMock,
        side_effect=RuntimeError(
            "OpenAI-compatible provider request failed (429): "
            "{'error': {'message': 'Rate limit reached for model llama-3.1-8b-instant "
            "on tokens per minute (TPM)', 'code': 'rate_limit_exceeded'}}"
        ),
    ):
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=DemoLiveTeaserResult(),
        ):
            with patch("app.services.demo_llm_retry.asyncio.sleep", new_callable=AsyncMock):
                response = demo_client.post(
                    "/demo/chat",
                    json={"session_id": "demo-session-rl", "message": "Hi", "messages": []},
                )

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["code"] == "provider_rate_limit"
    assert detail["limit_reached"] is False
    assert "rate-limited" in detail["message"].lower()


def test_demo_chat_stream_provider_rate_limit_error_event(demo_client: TestClient) -> None:
    with patch(
        "app.api.demo_routes.run_fast_chat",
        new_callable=AsyncMock,
        side_effect=RuntimeError("OpenAI-compatible provider request failed (429): rate_limit"),
    ):
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=DemoLiveTeaserResult(),
        ):
            with patch("app.services.demo_llm_retry.asyncio.sleep", new_callable=AsyncMock):
                with demo_client.stream(
                    "POST",
                    "/demo/chat/stream",
                    json={"session_id": "demo-session-stream-rl", "message": "Hi", "messages": []},
                ) as response:
                    raw = "".join(response.iter_text())

    events = _parse_sse_events(raw)
    error = next(e for e in events if e.get("type") == "error")
    assert error["detail"]["code"] == "provider_rate_limit"
    assert error["detail"]["limit_reached"] is False


def test_demo_chat_stream_final_event(demo_client: TestClient) -> None:
    fake_response = ChatResponse(message="Streamed hello", sources=[], workflow=None)

    with patch("app.api.demo_routes.run_fast_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=DemoLiveTeaserResult(),
        ):
            with demo_client.stream(
                "POST",
                "/demo/chat/stream",
                json={"session_id": "demo-session-stream", "message": "Hi", "messages": []},
            ) as response:
                assert response.status_code == 200
                raw = "".join(response.iter_text())

    events = _parse_sse_events(raw)
    assert any(event.get("type") == "final" for event in events)
    final = next(event for event in events if event.get("type") == "final")
    assert final["response"]["message"] == "Streamed hello"
    assert final["response"]["questions_used"] == 1
    assert final["response"]["full_app_url"] == "https://app.cura-i.com"


def test_demo_chat_stream_emits_status_for_live_teaser(demo_client: TestClient) -> None:
    fake_response = ChatResponse(message="Clear in Austin", sources=[], workflow=None)
    teaser = DemoLiveTeaserResult(
        intent="weather",
        context="## Live context\nClear",
        blocks=[ContentBlock(type="weather", data={"source": "open-meteo"})],
        status_message="Fetching live weather…",
    )

    with patch("app.api.demo_routes.run_fast_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=teaser,
        ):
            with demo_client.stream(
                "POST",
                "/demo/chat/stream",
                json={
                    "session_id": "demo-session-stream-live",
                    "message": "What's the weather in Austin?",
                    "messages": [],
                },
            ) as response:
                raw = "".join(response.iter_text())

    events = _parse_sse_events(raw)
    status_messages = [e.get("message") for e in events if e.get("type") == "status"]
    assert "Fetching live weather…" in status_messages
    assert "Writing reply…" in status_messages
    assert any(e.get("type") == "final" for e in events)


def test_demo_chat_stream_quota_error_event(demo_client: TestClient) -> None:
    fake_response = ChatResponse(message="ok", sources=[], workflow=None)

    with patch("app.api.demo_routes.run_fast_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
        with patch(
            "app.api.demo_routes.fetch_demo_live_teaser",
            new_callable=AsyncMock,
            return_value=DemoLiveTeaserResult(),
        ):
            for _ in range(2):
                demo_client.post(
                    "/demo/chat",
                    json={"session_id": "demo-session-stream-quota", "message": "Hi", "messages": []},
                )
            with demo_client.stream(
                "POST",
                "/demo/chat/stream",
                json={
                    "session_id": "demo-session-stream-quota",
                    "message": "Too many",
                    "messages": [],
                },
            ) as response:
                raw = "".join(response.iter_text())

    events = _parse_sse_events(raw)
    assert any(e.get("type") == "error" for e in events)
    error = next(e for e in events if e.get("type") == "error")
    assert error["detail"]["limit_reached"] is True
    assert error["detail"]["questions_remaining"] == 0
