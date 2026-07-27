"""Tests for the Agent Lab Phase 6 memory agent (pure functions + store)."""

from __future__ import annotations

import tempfile

from app.services.learn_agents.memory_agent import LabMemoryStore, _parse_facts


def test_parse_facts_extracts_json_array():
    text = 'Sure, here you go:\n["Prefers concise answers", "Building a CLI tool"]'
    assert _parse_facts(text) == ["Prefers concise answers", "Building a CLI tool"]


def test_parse_facts_empty_array():
    assert _parse_facts("[]") == []


def test_parse_facts_invalid_json_returns_empty():
    assert _parse_facts("not json at all") == []


def test_parse_facts_non_list_json_returns_empty():
    assert _parse_facts('{"a": 1}') == []


def test_parse_facts_caps_at_ten():
    items = [f"fact {i}" for i in range(15)]
    text = str(items).replace("'", '"')
    assert len(_parse_facts(text)) == 10


def test_store_add_and_recall_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        store = LabMemoryStore(file_path=f"{tmp}/facts.json")
        store.add_facts("user-1", ["Likes terse replies"])
        store.add_facts("user-1", ["Working on a Python project", "Likes terse replies"])
        facts = store.get_facts("user-1")
        assert facts == ["Likes terse replies", "Working on a Python project"]
        block = store.get_recall_block("user-1")
        assert "Likes terse replies" in block
        assert block.startswith("Known about this user:")


def test_store_recall_empty_for_unknown_user():
    with tempfile.TemporaryDirectory() as tmp:
        store = LabMemoryStore(file_path=f"{tmp}/facts.json")
        assert store.get_recall_block("nobody") == ""
        assert store.get_facts("nobody") == []
