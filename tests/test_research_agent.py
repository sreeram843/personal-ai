"""Tests for the Agent Lab Phase 3 ReAct research agent (pure functions only)."""

from __future__ import annotations

from app.services.learn_agents.research_agent import (
    _ACTION_RE,
    _FINAL_ANSWER_RE,
    _format_results,
)


def test_action_regex_extracts_query():
    text = "Thought: I should look this up.\nAction: search[capital of France]"
    match = _ACTION_RE.search(text)
    assert match is not None
    assert match.group(1) == "capital of France"


def test_action_regex_no_match_on_final_answer():
    text = "Thought: I know this.\nFinal Answer: Paris."
    assert _ACTION_RE.search(text) is None


def test_final_answer_regex_extracts_answer():
    text = "Thought: done reasoning.\nFinal Answer: The answer is 42."
    match = _FINAL_ANSWER_RE.search(text)
    assert match is not None
    assert match.group(1).strip() == "The answer is 42."


def test_format_results_empty():
    assert _format_results([]) == "No results found."


def test_format_results_limits_to_five_and_formats():
    results = [
        {"title": f"T{i}", "body": f"B{i}", "href": f"https://x/{i}"} for i in range(8)
    ]
    formatted = _format_results(results)
    lines = formatted.splitlines()
    assert len(lines) == 5
    assert lines[0] == "- T0: B0 (https://x/0)"
