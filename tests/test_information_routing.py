"""Tests for web-research and smart-mode routing heuristics."""

import pytest

from app.services.information_routing import (
    decompose_research_queries,
    is_corpus_overview_query,
    is_document_grounded_query,
    is_external_web_lookup_query,
    is_quick_social_utterance,
    is_trivial_chitchat,
    prefers_tool_agent_for_query,
    should_route_chat_toward_orchestrated,
    should_route_chat_toward_tools,
    should_route_smart_toward_workflow,
    should_run_web_research,
)
from app.services.web_search import should_prioritize_fresh_web_data


@pytest.mark.parametrize(
    "query, expected",
    [
        ("", True),  # empty: treat as no meaningful search
        ("ok", True),
        ("  Thanks  ", True),
        ("hello", True),
        ("Explain Rust ownership in detail", False),
    ],
)
def test_is_trivial_chitchat(query: str, expected: bool) -> None:
    assert is_trivial_chitchat(query) is expected


@pytest.mark.parametrize(
    "query, expected",
    [
        ("hi", True),
        ("Hello there you", False),  # not in quick social set
    ],
)
def test_is_quick_social(query: str, expected: bool) -> None:
    assert is_quick_social_utterance(query) is expected


def test_empty_retrieval_does_not_force_web() -> None:
    assert should_prioritize_fresh_web_data("What is a monad?") is False
    assert should_run_web_research("What is a monad?", has_internal_hits=False) is False


def test_freshness_still_runs_researcher_without_docs() -> None:
    assert should_run_web_research("What is the AAPL stock price today?", has_internal_hits=False) is True


def test_with_internal_docs_researcher_only_for_fresh() -> None:
    assert should_run_web_research("Summarize our NDA from last year", has_internal_hits=True) is False
    assert should_run_web_research("Summarize the Q3 report from the archive", has_internal_hits=True) is False
    assert should_run_web_research("Latest margin requirements in the contract", has_internal_hits=True) is True


@pytest.mark.parametrize(
    "query, expect_workflow",
    [
        ("hi", False),
        ("AAPL price", False),  # short; static pipeline + optional live/short data path
        ("What is the latest news on NVIDIA and AMD compare their outlooks", True),
    ],
)
def test_smart_workflow_tiering(query: str, expect_workflow: bool) -> None:
    assert should_route_smart_toward_workflow(query) is expect_workflow


def test_chat_execution_tiering() -> None:
    assert should_route_chat_toward_tools("What is NVDA trading at today?") is True
    assert should_route_chat_toward_orchestrated("What is NVDA trading at today?") is False
    complex_query = "Compare three deployment strategies for multi-tenant RAG and recommend trade-offs"
    assert should_route_chat_toward_orchestrated(complex_query) is True
    assert should_route_chat_toward_tools(complex_query) is False
    assert is_document_grounded_query("Summarize my uploaded notes with citations") is True
    assert is_corpus_overview_query("What are the main themes across my documents?") is True
    assert is_corpus_overview_query("What is NVDA trading at today?") is False


def test_external_web_lookup_routes_to_tools_not_orchestrated() -> None:
    bbq_query = (
        "What is best bbq in Austin and compare that with best bbq in Dallas? "
        "Get a winner from above and compare it with Joes bbq KC"
    )
    assert is_external_web_lookup_query(bbq_query) is True
    assert should_run_web_research(bbq_query, has_internal_hits=False) is True
    assert should_route_chat_toward_orchestrated(bbq_query) is False
    assert prefers_tool_agent_for_query(bbq_query) is True


def test_decompose_research_queries_splits_comparisons() -> None:
    query = (
        "What is best bbq in Austin and compare that with best bbq in Dallas? "
        "Get a winner from above and compare it with Joes bbq KC"
    )
    parts = decompose_research_queries(query)
    assert len(parts) >= 2
    assert any("Austin" in part for part in parts)
    assert any("Dallas" in part for part in parts)
