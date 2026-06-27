"""Tests for chat message persistence to Postgres."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import routes as routes_mod
from app.core.config import Settings
from app.core.deps import get_run_store
from app.schemas.chat import ChatResponse
from app.services.conversation_store import list_messages_for_conversation


@pytest.fixture
def chat_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def fake_short_circuit(**kwargs: object) -> ChatResponse | None:
        return None

    monkeypatch.setattr(routes_mod, "_live_data_short_circuit", fake_short_circuit)

    async def fake_run_orchestrated_mode(**kwargs: object) -> ChatResponse:
        return ChatResponse(message="persisted assistant reply", sources=[])

    monkeypatch.setattr(routes_mod, "run_orchestrated_mode", fake_run_orchestrated_mode)
    monkeypatch.setattr(routes_mod, "get_settings", lambda: Settings(enable_tool_agent=False))
    from app.main import app

    return TestClient(app)


def test_chat_creates_conversation_and_persists_messages(chat_client: TestClient, db_session) -> None:
    response = chat_client.post("/chat", json={"message": "Hello persistence"})
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "persisted assistant reply"
    assert body["conversation_id"]

    conversation_id = uuid.UUID(body["conversation_id"])
    from app.core.auth import DEV_USER_ID

    messages = list_messages_for_conversation(db_session, DEV_USER_ID, conversation_id)
    assert messages is not None
    assert len(messages) == 2
    assert messages[0].role.value == "user"
    assert messages[0].content == "Hello persistence"
    assert messages[1].role.value == "assistant"
    assert messages[1].content == "persisted assistant reply"


def test_chat_appends_to_existing_conversation(chat_client: TestClient, db_session) -> None:
    first = chat_client.post("/chat", json={"message": "First turn"})
    conversation_id = first.json()["conversation_id"]

    second = chat_client.post(
        "/chat",
        json={"message": "Second turn", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id

    from app.core.auth import DEV_USER_ID

    messages = list_messages_for_conversation(db_session, DEV_USER_ID, uuid.UUID(conversation_id))
    assert messages is not None
    assert len(messages) == 4
    assert messages[-2].content == "Second turn"
    assert messages[-1].content == "persisted assistant reply"


def test_smart_chat_returns_conversation_id(chat_client: TestClient) -> None:
    class _StubRunStore:
        def create_run(self, **kwargs: object):
            class _Run:
                run_id = "run-test"

            return _Run()

        def update_run_status(self, *args: object, **kwargs: object) -> None:
            return None

    from app.main import app

    app.dependency_overrides[get_run_store] = lambda: _StubRunStore()
    try:
        response = chat_client.post("/smart_chat", json={"message": "Route me"})
        assert response.status_code == 200
        assert response.json()["conversation_id"]
    finally:
        app.dependency_overrides.pop(get_run_store, None)
