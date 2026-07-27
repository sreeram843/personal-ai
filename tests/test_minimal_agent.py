"""Tests for the Agent Lab Phase 1 minimal agent (pure functions only)."""

from __future__ import annotations

from app.services.learn_agents.minimal_agent import _extract_message, calculate


def test_calculate_basic_arithmetic():
    assert calculate("(2 + 3) * 4") == "20"
    assert calculate("10 / 4") == "2.5"
    assert calculate("-7 + 2") == "-5"


def test_calculate_rejects_non_arithmetic():
    assert calculate("__import__('os')").startswith("ERROR")
    assert calculate("'a' * 99").startswith("ERROR")
    assert calculate("2 ** 1000").startswith("ERROR")


def test_extract_message_openai_shape():
    raw = {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
    assert _extract_message(raw) == {"role": "assistant", "content": "hi"}


def test_extract_message_ollama_shape():
    raw = {"message": {"role": "assistant", "content": "hello"}}
    assert _extract_message(raw) == {"role": "assistant", "content": "hello"}


def test_extract_message_empty():
    assert _extract_message({}) == {}
