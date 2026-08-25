"""Implicit per-user skill preference counts."""

from __future__ import annotations

from pathlib import Path

from app.services.skill_implicit import SkillImplicitStore, build_skill_implicit_store
from app.services.skill_loader import SkillCatalog, SkillStore, build_skill_catalog, build_skill_store
from app.services.skill_resolution import resolve_active_skill


def _write_skill(root: Path, skill_id: str, *, triggers: list[str], name: str | None = None) -> None:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True)
    trigger_lines = "\n".join(f"  - {t}" for t in triggers)
    (skill_dir / "SKILL.md").write_text(
        f"""---
id: {skill_id}
name: {name or skill_id}
triggers:
{trigger_lines}
---
Body
""",
        encoding="utf-8",
    )


def _setup(tmp_path: Path) -> tuple[SkillCatalog, SkillStore, SkillImplicitStore]:
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "alpha", triggers=["shared brief", "alpha only"])
    _write_skill(skills_root, "beta", triggers=["shared brief", "beta only"])
    store = build_skill_store(file_path=str(tmp_path / "user_skills.json"))
    implicit = build_skill_implicit_store(file_path=str(tmp_path / "skill_implicit.json"))
    catalog = build_skill_catalog(
        bundled_root=str(skills_root),
        store=store,
        implicit=implicit,
    )
    return catalog, store, implicit


def test_cold_start_single_trigger_unchanged(tmp_path: Path) -> None:
    catalog, _, _ = _setup(tmp_path)
    resolved = catalog.resolve("Give me an alpha only update", user_id="user-a")
    assert resolved is not None
    assert resolved.skill.id == "alpha"
    assert resolved.matched_by == "alpha only"


def test_ambiguous_query_prefers_historically_used_skill(tmp_path: Path) -> None:
    catalog, _, implicit = _setup(tmp_path)

    cold = catalog.resolve("run a shared brief", user_id="user-a")
    assert cold is not None
    assert cold.skill.id == "alpha"

    for _ in range(3):
        implicit.record("user-a", "beta")

    preferred = catalog.resolve("run a shared brief", user_id="user-a")
    assert preferred is not None
    assert preferred.skill.id == "beta"


def test_disabled_pref_still_wins_over_implicit(tmp_path: Path) -> None:
    catalog, store, implicit = _setup(tmp_path)
    for _ in range(5):
        implicit.record("user-a", "alpha")

    store.set_bundled_preference("user-a", "alpha", enabled=False)
    resolved = catalog.resolve("run a shared brief", user_id="user-a")
    assert resolved is not None
    assert resolved.skill.id == "beta"


def test_user_b_counts_do_not_affect_user_a(tmp_path: Path) -> None:
    catalog, _, implicit = _setup(tmp_path)
    for _ in range(4):
        implicit.record("user-b", "beta")

    for_a = catalog.resolve("run a shared brief", user_id="user-a")
    assert for_a is not None
    assert for_a.skill.id == "alpha"

    for_b = catalog.resolve("run a shared brief", user_id="user-b")
    assert for_b is not None
    assert for_b.skill.id == "beta"


def test_resolve_active_skill_records_trigger_not_assistant(tmp_path: Path) -> None:
    catalog, store, implicit = _setup(tmp_path)

    by_trigger = resolve_active_skill(
        catalog,
        user_id="user-a",
        query="Give me an alpha only update",
    )
    assert by_trigger is not None
    assert by_trigger.skill.id == "alpha"
    assert implicit.preferred_among("user-a", ["alpha", "beta"]) == "alpha"

    custom = store.create(
        user_id="user-a",
        name="Custom",
        description="",
        triggers=[],
        allowed_tools=[],
        system_addendum="Custom instructions",
        pick_only=True,
    )
    by_assistant = resolve_active_skill(
        catalog,
        user_id="user-a",
        query="unrelated text",
        assistant_id=custom.id,
    )
    assert by_assistant is not None
    assert by_assistant.matched_by == "assistant"
    assert implicit.preferred_among("user-a", [custom.id]) is None


def test_preferred_among_tie_returns_none(tmp_path: Path) -> None:
    implicit = SkillImplicitStore(file_path=str(tmp_path / "skill_implicit.json"))
    implicit.record("user-a", "alpha")
    implicit.record("user-a", "beta")
    assert implicit.preferred_among("user-a", ["alpha", "beta"]) is None
    assert implicit.preferred_among("user-a", ["alpha", "beta", "gamma"]) is None
