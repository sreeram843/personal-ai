"""Tests for chat execution strategy (Phase A fast path + tool agent)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import routes as routes_mod
from app.core.config import Settings
from app.main import app
from app.services import chat_execution as chat_execution_mod
from app.schemas.chat import ChatResponse
from app.services.chat_execution import resolve_chat_execution_strategy


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def skip_live_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_shortcut(**kwargs: object) -> None:
        return None

    monkeypatch.setattr(routes_mod, "_live_data_short_circuit", no_shortcut)


@pytest.mark.parametrize(
    ("query", "fast_chat", "langchain", "expected"),
    [
        ("hi", True, True, "fast"),
        ("thanks", True, True, "fast"),
        ("What is NVDA trading at today?", True, True, "tools"),
        ("Explain quantum computing", True, False, "orchestrated"),
        ("ok", True, False, "fast"),
    ],
)
def test_resolve_chat_execution_strategy(
    query: str,
    fast_chat: bool,
    langchain: bool,
    expected: str,
) -> None:
    settings = Settings(enable_fast_chat=fast_chat, enable_langchain_agent=langchain)
    assert resolve_chat_execution_strategy(query, settings) == expected


def test_list_tools_endpoint(client: TestClient) -> None:
    response = client.get("/tools")
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "chat_agent"
    tool_ids = {item["tool_id"] for item in body["tools"]}
    assert "web_search" in tool_ids
    assert "fx_rate" in tool_ids


def test_fast_chat_path_for_greeting(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fast_chat(**kwargs: object) -> ChatResponse:
        return ChatResponse(message="from-fast-chat", sources=[])

    monkeypatch.setattr(chat_execution_mod, "run_fast_chat", fake_fast_chat)

    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["message"] == "from-fast-chat"


def test_tool_agent_path_for_fresh_query(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_agent(**kwargs: object) -> str:
        return "from-tool-agent"

    monkeypatch.setattr(chat_execution_mod, "run_langchain_agent", fake_agent)

    response = client.post("/chat", json={"message": "Summarize the plot of Dune in two sentences"})
    assert response.status_code == 200
    assert "from-tool-agent" in response.json()["message"]


def test_tool_agent_falls_back_to_fast_chat_on_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_agent(**kwargs: object) -> str:
        raise RuntimeError("tool calling not supported")

    async def fake_fast_chat(**kwargs: object) -> ChatResponse:
        return ChatResponse(message="from-fast-chat-fallback", sources=[])

    monkeypatch.setattr(chat_execution_mod, "run_langchain_agent", failing_agent)
    monkeypatch.setattr(chat_execution_mod, "run_fast_chat", fake_fast_chat)

    response = client.post("/chat", json={"message": "Summarize the plot of Dune in two sentences"})
    assert response.status_code == 200
    assert response.json()["message"] == "from-fast-chat-fallback"


def test_orchestrated_fallback_when_tools_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        chat_execution_mod,
        "get_settings",
        lambda: Settings(enable_fast_chat=False, enable_langchain_agent=False),
    )

    class FakeService:
        async def run_mode(self, **kwargs: object) -> ChatResponse:
            return ChatResponse(message="from-orchestrated", sources=[])

    import app.services.orchestrated_runner as runner_mod

    monkeypatch.setattr(runner_mod, "build_orchestrated_service", lambda **kw: FakeService())

    response = client.post("/chat", json={"message": "Explain Rust ownership in detail"})
    assert response.status_code == 200
    assert response.json()["message"] == "from-orchestrated"
