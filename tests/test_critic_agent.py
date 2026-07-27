"""Tests for the Agent Lab Phase 5 drafter+critic score parser."""

from __future__ import annotations

from app.services.learn_agents.critic_agent import _parse_scores


def test_parse_scores_extracts_all_three():
    text = (
        "Completeness: 7/10\n"
        "Clarity: 9/10\n"
        "Directness: 4/10\n"
        "Feedback:\n"
        "- Be more specific about X.\n"
        "- Drop the hedging in paragraph two."
    )
    scores = _parse_scores(text)
    assert scores == {"Completeness": 7, "Clarity": 9, "Directness": 4}


def test_parse_scores_is_case_insensitive():
    text = "completeness: 5/10\nCLARITY: 6/10\ndirectness: 8/10"
    scores = _parse_scores(text)
    assert scores == {"Completeness": 5, "Clarity": 6, "Directness": 8}


def test_parse_scores_handles_missing_scores():
    text = "The draft looks fine overall, no formal scoring given."
    assert _parse_scores(text) == {}
