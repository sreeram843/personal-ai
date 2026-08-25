"""Tests for bundled skills shipped in the repo skills/ directory."""

from __future__ import annotations

from pathlib import Path

from app.services.builtin_tools import CHAT_AGENT_ROLE, register_builtin_tools
from app.services.skill_context import activate_skill_context, deactivate_skill_context
from app.services.skill_loader import SkillCatalog, build_skill_catalog, build_skill_store
from app.services.tool_invocation import list_agent_tool_specs
from app.services.tool_registry import ToolRegistry
from app.services.web_search import WebSearchService

REPO_SKILLS = Path(__file__).resolve().parents[1] / "skills"

EXPECTED_SKILLS: dict[str, dict[str, list[str]]] = {
    "live-brief": {
        "triggers": ["live brief", "morning briefing", "daily brief"],
        "allowed_tools": ["weather", "market_price", "get_crypto_price", "news"],
    },
    "market-pulse": {
        "triggers": ["market pulse", "portfolio check"],
        "allowed_tools": ["market_price", "get_crypto_price", "fx_rate"],
    },
    "trip-check": {
        "triggers": ["trip check", "travel status"],
        "allowed_tools": [
            "get_flight_status",
            "get_traffic_eta",
            "get_transit_arrivals",
            "weather",
        ],
    },
    "doc-digest": {
        "triggers": ["digest this", "summarize my uploads"],
        "allowed_tools": ["search_documents"],
    },
    "research-memo": {
        "triggers": ["research memo", "write me a brief on"],
        "allowed_tools": ["web_research", "web_search"],
    },
    "package-watch": {
        "triggers": [
            "where's my package",
            "where is my package",
            "delivery status",
        ],
        "allowed_tools": ["get_package_tracking"],
    },
}


def _catalog(tmp_path: Path) -> SkillCatalog:
    store = build_skill_store(file_path=str(tmp_path / "user_skills.json"))
    return build_skill_catalog(bundled_root=str(REPO_SKILLS), store=store)


def test_bundled_skill_ids_are_present(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    ids = {item.id for item in catalog.list_for_user("user-1")}
    assert EXPECTED_SKILLS.keys() <= ids


def test_bundled_skill_triggers_resolve(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    for skill_id, expected in EXPECTED_SKILLS.items():
        for phrase in expected["triggers"]:
            resolved = catalog.resolve(phrase, user_id="user-1")
            assert resolved is not None, f"no skill for trigger {phrase!r}"
            assert resolved.skill.id == skill_id, f"{phrase!r} mapped to {resolved.skill.id}"
            assert resolved.matched_by == phrase


def test_bundled_skill_allowed_tools(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    by_id = {item.id: item for item in catalog.list_for_user("user-1")}
    for skill_id, expected in EXPECTED_SKILLS.items():
        assert by_id[skill_id].allowed_tools == expected["allowed_tools"]


def test_list_agent_tool_specs_filters_to_skill_allowed_tools(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    skill = catalog.get_by_id("user-1", "market-pulse")
    assert skill is not None

    registry = ToolRegistry()
    register_builtin_tools(registry, WebSearchService())
    unfiltered = list_agent_tool_specs(registry, role=CHAT_AGENT_ROLE)
    assert "weather" in unfiltered
    assert "market_price" in unfiltered

    token = activate_skill_context(allowed_tools=skill.allowed_tools, skill_name=skill.name)
    try:
        filtered = list_agent_tool_specs(registry, role=CHAT_AGENT_ROLE)
        assert set(filtered) == set(skill.allowed_tools) & set(unfiltered)
        assert "weather" not in filtered
        assert set(skill.allowed_tools) <= set(filtered)
    finally:
        deactivate_skill_context(token)
