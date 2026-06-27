"""Accuracy-style evaluation for smart routing and research gating."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.routes import _select_smart_mode
from app.schemas.chat import ChatMessage, ChatRequest
from app.services.information_routing import (
    is_quick_social_utterance,
    should_route_smart_toward_workflow,
    should_run_web_research,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "routing_golden.json"
GOLDEN_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case["query"][:48])
def test_smart_mode_routing_golden_fixture(case: dict) -> None:
    payload = ChatRequest(messages=[ChatMessage(role="user", content=case["query"])])
    assert _select_smart_mode(payload) == case["expected_mode"]
    assert should_run_web_research(case["query"], has_internal_hits=False) == case["expect_web_research"]
    assert should_route_smart_toward_workflow(case["query"]) == case["expect_workflow"]


@pytest.mark.parametrize(
    ("query", "expected_mode"),
    [
        ("hi", "chat"),
        ("thanks", "chat"),
        ("Rewrite this email to be friendlier", "rag"),
        ("Summarize my uploaded notes with citations", "rag"),
        (
            "Compare three deployment strategies for multi-tenant RAG and recommend a roadmap with trade-offs",
            "workflow",
        ),
        (
            "What is best bbq in Austin and compare that with best bbq in Dallas? "
            "Get a winner and compare it with Joes bbq KC",
            "rag",
        ),
    ],
)
def test_smart_mode_routing_golden_cases(query: str, expected_mode: str) -> None:
    payload = ChatRequest(messages=[ChatMessage(role="user", content=query)])
    assert _select_smart_mode(payload) == expected_mode


def test_social_utterances_skip_workflow_and_web() -> None:
    assert is_quick_social_utterance("hello") is True
    assert should_run_web_research("hello", has_internal_hits=False) is False


def test_fresh_complex_queries_prefer_workflow() -> None:
    query = "Compare current EUR/USD and GBP/USD exchange rates and explain the implications for tomorrow"
    assert should_route_smart_toward_workflow(query) is True


def test_web_research_is_not_triggered_for_empty_corpus_alone() -> None:
    assert should_run_web_research("Explain how cosine similarity works in embeddings", has_internal_hits=False) is False
