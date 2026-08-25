"""Tests for OpenAI-compatible /v1 endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.schemas.chat import ChatResponse
from app.services.openai_compat import chat_request_from_openai, strategy_override_for_model
from tests.conftest import apply_db_auth_overrides


def test_strategy_override_for_model() -> None:
    assert strategy_override_for_model("curai-tools") == "tools"
    assert strategy_override_for_model("curai-fast") == "fast"
    assert strategy_override_for_model("curai-default") is None


def test_chat_request_from_openai_maps_messages_and_metadata() -> None:
    payload = chat_request_from_openai(
        {
            "model": "curai-tools",
            "messages": [{"role": "user", "content": "Hello"}],
            "metadata": {"assistant_id": "live-brief", "conversation_id": "conv-1"},
        }
    )
    assert payload.messages[-1].content == "Hello"
    assert payload.conversation_id == "conv-1"
    assert payload.options == {"force_strategy": "tools", "assistant_id": "live-brief"}


def test_list_models(client: TestClient) -> None:
    response = client.get("/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    ids = {item["id"] for item in body["data"]}
    assert "curai-default" in ids
    assert "curai-tools" in ids


@pytest.fixture
def disabled_openai_client(db_session) -> TestClient:
    app = create_app()
    settings = apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: Settings(
        **{**settings.model_dump(), "enable_openai_api": False}
    )
    return TestClient(app)


def test_openai_api_disabled(disabled_openai_client: TestClient) -> None:
    response = disabled_openai_client.get("/v1/models")
    assert response.status_code == 404


def test_chat_completions(client: TestClient) -> None:
    fake_response = ChatResponse(message="Hello from CurieAI", sources=[], workflow=None)

    with patch("app.api.openai_routes.run_persisted_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "curai-default",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Hello from CurieAI"
    mock_chat.assert_awaited_once()
