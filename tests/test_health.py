"""Tests for health and readiness endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_liveness():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body


def test_ready_when_dependencies_ok():
    client = TestClient(create_app())
    with patch("app.api.routes.readiness_report", new_callable=AsyncMock) as mock_ready:
        mock_ready.return_value = {
            "status": "ready",
            "app": "personal-ai",
            "checks": {"ollama": {"status": "ok"}, "qdrant": {"status": "ok"}},
        }
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_returns_503_when_not_ready():
    client = TestClient(create_app())
    with patch("app.api.routes.readiness_report", new_callable=AsyncMock) as mock_ready:
        mock_ready.return_value = {
            "status": "not_ready",
            "app": "personal-ai",
            "checks": {"ollama": {"status": "error"}, "qdrant": {"status": "ok"}},
        }
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "not_ready"
