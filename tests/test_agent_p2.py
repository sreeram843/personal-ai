"""Tests for P2 agent features: skills, tasks, diagnostics helpers."""

from app.services.agent_task_store import build_agent_task_store
from app.services.skill_loader import build_skill_catalog, build_skill_store


def test_skill_catalog_loads_bundled_skill(tmp_path) -> None:
    skills_root = tmp_path / "skills"
    brief_dir = skills_root / "live-brief"
    brief_dir.mkdir(parents=True)
    (brief_dir / "SKILL.md").write_text(
        """---
id: live-brief
name: Live data brief
triggers:
  - morning briefing
allowed_tools:
  - weather
---
Brief the user.
""",
        encoding="utf-8",
    )
    store = build_skill_store(file_path=str(tmp_path / "user_skills.json"))
    catalog = build_skill_catalog(bundled_root=str(skills_root), store=store)
    skills = catalog.list_for_user("user-1")
    assert any(item.id == "live-brief" for item in skills)
    resolved = catalog.resolve("Give me a morning briefing", user_id="user-1")
    assert resolved is not None
    assert resolved.skill.id == "live-brief"


def test_skill_slash_command_resolution(tmp_path) -> None:
    skills_root = tmp_path / "skills"
    brief_dir = skills_root / "live-brief"
    brief_dir.mkdir(parents=True)
    (brief_dir / "SKILL.md").write_text(
        """---
id: live-brief
name: Live data brief
---
Body
""",
        encoding="utf-8",
    )
    store = build_skill_store(file_path=str(tmp_path / "user_skills.json"))
    catalog = build_skill_catalog(bundled_root=str(skills_root), store=store)
    resolved = catalog.resolve("/live-brief", user_id="user-1")
    assert resolved is not None


def test_agent_task_store_planned_tools(tmp_path) -> None:
    store = build_agent_task_store(file_path=str(tmp_path / "tasks.json"))
    created = store.record_planned_tools(
        user_id="user-1",
        conversation_id="conv-1",
        planned_tools=[{"tool_id": "weather", "name": "Weather", "reason": "Plan mode"}],
    )
    assert len(created) == 1
    tasks = store.list_for_user("user-1")
    assert tasks[0].source == "planned_tool"
    updated = store.update_status(tasks[0].id, user_id="user-1", status="completed")
    assert updated is not None
    assert updated.status == "completed"


def test_bundled_skill_preference_toggle(tmp_path) -> None:
    skills_root = tmp_path / "skills"
    brief_dir = skills_root / "live-brief"
    brief_dir.mkdir(parents=True)
    (brief_dir / "SKILL.md").write_text(
        """---
id: live-brief
name: Live data brief
---
Body
""",
        encoding="utf-8",
    )
    store = build_skill_store(file_path=str(tmp_path / "user_skills.json"))
    catalog = build_skill_catalog(bundled_root=str(skills_root), store=store)
    store.set_bundled_preference("user-1", "live-brief", enabled=False)
    skill = next(item for item in catalog.list_for_user("user-1") if item.id == "live-brief")
    assert skill.enabled is False
