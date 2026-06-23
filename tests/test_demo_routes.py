"""Tests for public portfolio demo API."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.schemas.chat import ChatResponse
from tests.conftest import apply_db_auth_overrides


@pytest.fixture
def demo_client(db_session) -> TestClient:
    app = create_app()
    settings = apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: Settings(
        **{**settings.model_dump(), "demo_enabled": True, "demo_max_questions": 2, "demo_full_app_url": "https://app.cura-i.com"}
    )
    return TestClient(app)


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


def test_demo_chat_increments_quota(demo_client: TestClient) -> None:
    fake_response = ChatResponse(message="Hello from demo", sources=[], workflow=None)

    with patch("app.api.demo_routes.run_fast_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_response
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
