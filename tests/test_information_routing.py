"""Tests for web-research and smart-mode routing heuristics."""

import pytest

from app.services.information_routing import (
    is_quick_social_utterance,
    is_trivial_chitchat,
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
