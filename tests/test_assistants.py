"""Tests for assistants API and explicit assistant resolution."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.skill_loader import build_skill_catalog, build_skill_store
from app.services.skill_resolution import resolve_active_skill


def test_list_assistants_includes_default(client: TestClient) -> None:
    response = client.get("/agent/assistants")
    assert response.status_code == 200
    assistants = response.json()["assistants"]
    assert any(item["id"] == "default" and item["is_default"] for item in assistants)


def test_create_and_delete_assistant(client: TestClient) -> None:
    create_response = client.post(
        "/agent/assistants",
        json={
            "name": "Research helper",
            "description": "Focused on citations",
            "instructions": "Always cite sources.",
            "allowed_tools": ["web_search"],
            "pick_only": True,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Research helper"
    assert created["pick_only"] is True
    assert created["allowed_tools"] == ["web_search"]

    list_response = client.get("/agent/assistants")
    assert any(item["id"] == created["id"] for item in list_response.json()["assistants"])

    delete_response = client.delete(f"/agent/assistants/{created['id']}")
    assert delete_response.status_code == 204


def test_create_conversation_with_assistant_id(client: TestClient) -> None:
    assistant = client.post(
        "/agent/assistants",
        json={"name": "Briefing", "instructions": "Keep it short.", "pick_only": True},
    ).json()

    create_response = client.post(
        "/conversations",
        json={"title": "Brief chat", "assistant_id": assistant["id"]},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["assistant_id"] == assistant["id"]


def test_default_assistant_id_is_normalized(client: TestClient) -> None:
    response = client.post("/conversations", json={"assistant_id": "default"})
    assert response.status_code == 201
    assert response.json()["assistant_id"] is None


def test_explicit_assistant_resolution(tmp_path) -> None:
    skills_root = tmp_path / "skills"
    brief_dir = skills_root / "live-brief"
    brief_dir.mkdir(parents=True)
    (brief_dir / "SKILL.md").write_text(
        """---
id: live-brief
name: Live data brief
triggers:
  - morning briefing
---
Brief the user.
""",
        encoding="utf-8",
    )
    store = build_skill_store(file_path=str(tmp_path / "user_skills.json"))
    catalog = build_skill_catalog(bundled_root=str(skills_root), store=store)

    by_trigger = resolve_active_skill(
        catalog,
        user_id="user-1",
        query="Give me a morning briefing",
        assistant_id=None,
    )
    assert by_trigger is not None
    assert by_trigger.skill.id == "live-brief"
    assert by_trigger.matched_by == "morning briefing"

    custom = store.create(
        user_id="user-1",
        name="Custom",
        description="",
        triggers=[],
        allowed_tools=[],
        system_addendum="Custom instructions",
        pick_only=True,
    )
    by_assistant = resolve_active_skill(
        catalog,
        user_id="user-1",
        query="unrelated text",
        assistant_id=custom.id,
    )
    assert by_assistant is not None
    assert by_assistant.skill.id == custom.id
    assert by_assistant.matched_by == "assistant"
