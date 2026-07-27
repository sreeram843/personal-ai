"""Tests for the Agent Lab Phase 7 tool-builder's pure/subprocess helpers."""

from __future__ import annotations

from app.services.learn_agents.tool_builder_agent import _run_tool_call, _signature_of


def test_signature_of_extracts_name_and_params():
    code = "def count_vowels(word: str) -> int:\n    return sum(1 for c in word if c in 'aeiou')\n"
    name, signature = _signature_of(code)
    assert name == "count_vowels"
    assert "word" in signature


def test_signature_of_returns_none_for_no_function():
    name, signature = _signature_of("x = 1 + 1\n")
    assert name is None
    assert signature == ""


def test_run_tool_call_executes_with_arguments():
    code = "def add(a, b):\n    return a + b\n"
    ok, output = _run_tool_call(code, "add", {"a": 2, "b": 3})
    assert ok is True
    assert output == "5"


def test_run_tool_call_reports_error_on_bad_arguments():
    code = "def add(a, b):\n    return a + b\n"
    ok, output = _run_tool_call(code, "add", {"a": 2})
    assert ok is False
    assert "TypeError" in output or "add" in output
