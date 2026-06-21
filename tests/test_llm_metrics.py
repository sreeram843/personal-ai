"""Tests for LLM and chat Prometheus metrics."""

from fastapi.testclient import TestClient

from app.main import app


def test_llm_metrics_registered() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "model_response_seconds" in body
    assert "model_calls_total" in body
    assert "chat_reply_seconds" in body
    assert "chat_replies_total" in body
