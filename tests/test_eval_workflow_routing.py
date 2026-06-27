"""Workflow planner routing golden set (DeepPlanning-style prompts)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.information_routing import (
    should_route_chat_toward_orchestrated,
    should_route_smart_toward_workflow,
    should_run_web_research,
)

FIXTURES = Path(__file__).resolve().parent.parent / "eggplant" / "fixtures" / "workflow_golden.json"
GOLDEN_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))
LIVE_WORKFLOW_CASES = [case for case in GOLDEN_CASES if case.get("expect_orchestrated")]


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case["id"])
def test_workflow_routing_golden_fixture(case: dict) -> None:
    query = case["query"]
    assert should_route_chat_toward_orchestrated(query) == case["expect_orchestrated"]
    assert should_route_smart_toward_workflow(query) == case["expect_smart_workflow"]
    assert should_run_web_research(query, has_internal_hits=False) == case["expect_web_research"]


def test_workflow_live_smoke_case_ids() -> None:
    assert LIVE_WORKFLOW_CASES
    assert all(case["expect_orchestrated"] for case in LIVE_WORKFLOW_CASES)
