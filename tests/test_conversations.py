"""Tests for conversation CRUD APIs."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Conversation, Message, MessageRole
from tests.conftest import build_client


def test_list_conversations_empty(client: TestClient) -> None:
    response = client.get("/conversations")
    assert response.status_code == 200
    assert response.json() == {"conversations": []}


def test_create_and_list_conversation(client: TestClient) -> None:
    create_response = client.post("/conversations", json={"title": "Planning", "mode": "smart"})
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == "Planning"
    assert created["mode"] == "smart"
    assert created["message_count"] == 0

    list_response = client.get("/conversations")
    assert list_response.status_code == 200
    conversations = list_response.json()["conversations"]
    assert len(conversations) == 1
    assert conversations[0]["id"] == created["id"]
    assert conversations[0]["title"] == "Planning"


def test_list_messages_and_delete_conversation(client: TestClient, db_session) -> None:
    create_response = client.post("/conversations", json={"title": "Temp"})
    conversation_id = create_response.json()["id"]

    conversation = db_session.get(Conversation, uuid.UUID(conversation_id))
    conversation.messages.append(Message(role=MessageRole.user, content="Hello"))
    conversation.messages.append(Message(role=MessageRole.assistant, content="Hi there"))
    db_session.commit()

    messages_response = client.get(f"/conversations/{conversation_id}/messages")
    assert messages_response.status_code == 200
    body = messages_response.json()
    assert body["conversation_id"] == conversation_id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["content"] == "Hi there"

    delete_response = client.delete(f"/conversations/{conversation_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/conversations/{conversation_id}/messages")
    assert missing_response.status_code == 404


def test_conversations_are_isolated_between_users(db_session, auth_settings: Settings) -> None:
    from app.core.security import create_access_token
    from app.db.models import User, UserRole

    settings = auth_settings.model_copy(update={"auth_disabled": False})
    alice = User(email="alice@example.com", display_name="Alice", role=UserRole.user.value, is_active=True)
    bob = User(email="bob@example.com", display_name="Bob", role=UserRole.user.value, is_active=True)
    db_session.add_all([alice, bob])
    db_session.commit()

    alice_client = build_client(db_session, settings)
    bob_client = build_client(db_session, settings)
    try:
        alice_token = create_access_token(user_id=alice.id, settings=settings)
        bob_token = create_access_token(user_id=bob.id, settings=settings)
        alice_headers = {"Authorization": f"Bearer {alice_token}"}
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        created = alice_client.post(
            "/conversations",
            json={"title": "Alice private"},
            headers=alice_headers,
        )
        conversation_id = created.json()["id"]

        alice_messages = alice_client.get(
            f"/conversations/{conversation_id}/messages",
            headers=alice_headers,
        )
        assert alice_messages.status_code == 200

        bob_messages = bob_client.get(
            f"/conversations/{conversation_id}/messages",
            headers=bob_headers,
        )
        assert bob_messages.status_code == 404

        bob_delete = bob_client.delete(f"/conversations/{conversation_id}", headers=bob_headers)
        assert bob_delete.status_code == 404

        alice_still_there = alice_client.get("/conversations", headers=alice_headers)
        assert len(alice_still_there.json()["conversations"]) == 1
    finally:
        alice_client.close()
        bob_client.close()


def test_create_conversation_defaults(client: TestClient) -> None:
    response = client.post("/conversations", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New conversation"
    assert body["mode"] == "smart"


def test_update_conversation_rename(client: TestClient) -> None:
    create_response = client.post("/conversations", json={"title": "Old title"})
    conversation_id = create_response.json()["id"]

    update_response = client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "Renamed chat"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Renamed chat"
    assert updated["pinned"] is False

    list_response = client.get("/conversations")
    assert list_response.json()["conversations"][0]["title"] == "Renamed chat"


def test_update_conversation_pin_and_unpin(client: TestClient) -> None:
    create_response = client.post("/conversations", json={"title": "Pin me"})
    conversation_id = create_response.json()["id"]

    pin_response = client.patch(
        f"/conversations/{conversation_id}",
        json={"pinned": True},
    )
    assert pin_response.status_code == 200
    pinned = pin_response.json()
    assert pinned["pinned"] is True
    assert pinned["pinned_at"] is not None

    unpin_response = client.patch(
        f"/conversations/{conversation_id}",
        json={"pinned": False},
    )
    assert unpin_response.status_code == 200
    unpinned = unpin_response.json()
    assert unpinned["pinned"] is False
    assert unpinned["pinned_at"] is None


def test_update_conversation_requires_fields(client: TestClient) -> None:
    create_response = client.post("/conversations", json={"title": "No-op"})
    conversation_id = create_response.json()["id"]

    response = client.patch(f"/conversations/{conversation_id}", json={})
    assert response.status_code == 400


def test_pinned_conversations_sort_first(client: TestClient) -> None:
    first = client.post("/conversations", json={"title": "Recent A"}).json()["id"]
    second = client.post("/conversations", json={"title": "Recent B"}).json()["id"]

    client.patch(f"/conversations/{second}", json={"pinned": True})

    conversations = client.get("/conversations").json()["conversations"]
    assert conversations[0]["id"] == second
    assert conversations[0]["pinned"] is True
    assert conversations[1]["id"] == first
