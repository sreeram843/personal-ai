"""Tests for the Agent Lab Phase 4 coding agent's pure/subprocess helpers."""

from __future__ import annotations

from app.services.learn_agents.coding_agent import _extract_code, _run_in_subprocess


def test_extract_code_from_fenced_block():
    text = "Here you go:\n```python\ndef add(a, b):\n    return a + b\n```"
    assert _extract_code(text) == "def add(a, b):\n    return a + b"


def test_extract_code_falls_back_to_raw_text():
    text = "def add(a, b):\n    return a + b"
    assert _extract_code(text) == text


def test_extract_code_returns_none_for_blank():
    assert _extract_code("   \n") is None


def test_run_in_subprocess_passes_on_correct_code():
    code = "def add(a, b):\n    return a + b\n"
    tests = "assert add(2, 3) == 5\nprint('ok')\n"
    passed, output = _run_in_subprocess(code, tests)
    assert passed is True
    assert "ok" in output


def test_run_in_subprocess_reports_assertion_failure():
    code = "def add(a, b):\n    return a - b\n"
    tests = "assert add(2, 3) == 5\n"
    passed, output = _run_in_subprocess(code, tests)
    assert passed is False
    assert "AssertionError" in output


def test_run_in_subprocess_times_out_on_infinite_loop():
    code = "def spin():\n    while True:\n        pass\n"
    tests = "spin()\n"
    passed, output = _run_in_subprocess(code, tests)
    assert passed is False
    assert "TIMEOUT" in output
