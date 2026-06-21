from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import routes as routes_mod
from app.schemas.chat import ChatResponse
from app.services import chat_execution as chat_execution_mod


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def skip_live_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_shortcut(**kwargs: object) -> None:
        return None

    monkeypatch.setattr(routes_mod, "_live_data_short_circuit", no_shortcut)


def test_chat_endpoint_uses_chat_execution(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_execute_chat_mode(**kwargs: object) -> ChatResponse:
        return ChatResponse(message="from-chat-execution", sources=[])

    monkeypatch.setattr(chat_execution_mod, "execute_chat_mode", fake_execute_chat_mode)

    response = client.post("/chat", json={"message": "Explain recursion without live data keywords"})
    assert response.status_code == 200
    assert response.json()["message"] == "from-chat-execution"


def test_orchestrated_path_for_rag_mode(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, bool] = {"chat": False, "orchestrated": False}

    async def fake_execute_chat_mode(**kwargs: object) -> ChatResponse:  # pragma: no cover
        called["chat"] = True
        return ChatResponse(message="should-not-run", sources=[])

    async def fake_run_orchestrated_mode(**kw: object) -> ChatResponse:
        called["orchestrated"] = True
        return ChatResponse(message="from-orchestrated", sources=[])

    monkeypatch.setattr(chat_execution_mod, "execute_chat_mode", fake_execute_chat_mode)
    monkeypatch.setattr(routes_mod, "run_orchestrated_mode", fake_run_orchestrated_mode)

    response = client.post("/rag_chat", json={"message": "Summarize my uploaded notes"})
    assert response.status_code == 200
    assert called["chat"] is False
    assert called["orchestrated"] is True
    assert response.json()["message"] == "from-orchestrated"
