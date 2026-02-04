from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.persona_manager import get_persona_manager
from app.services.ollama import OllamaClient


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_persona_switch_endpoint(client: TestClient) -> None:
    response = client.post("/persona/switch", json={"name": "default"})
    assert response.status_code == 200
    assert response.json() == {"persona": "default"}

    response = client.get("/persona/active")
    assert response.status_code == 200
    assert response.json() == {"persona": "default"}


def test_persona_preview_contains_disclaimer(client: TestClient) -> None:
    client.post("/persona/switch", json={"name": "harvey_specter"})
    preview = client.get("/persona/preview")
    assert preview.status_code == 200
    payload = preview.json()
    assert "persona" in payload and payload["persona"] == "harvey_specter"
    assert "not legal advice" in payload["system_prompt"].lower()


def test_chat_filters_banned_words(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = get_persona_manager()
    manager.switch("harvey_specter")

    async def fake_chat(self: OllamaClient, messages: Any, *, options: Dict[str, Any] | None = None, stream: bool = False) -> Dict[str, Any]:
        return {"message": {"content": "This outcome is revolutionary."}}

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)

    with TestClient(app) as local_client:
        response = local_client.post("/chat", json={"message": "Say something bold"})
        assert response.status_code == 200
        message = response.json()["message"]
        assert "revolutionary" not in message.lower()
        assert "[redacted]" in message
