"""Tests for the Agent Lab Phase 6 eval harness (pure functions only)."""

from __future__ import annotations

from app.services.learn_agents.eval_harness import DEFAULT_TASKS, EvalResult, summarize


def test_default_tasks_have_unique_ids():
    ids = [task.id for task in DEFAULT_TASKS]
    assert len(ids) == len(set(ids))


def test_default_tasks_cover_all_agent_types():
    agents = {task.agent for task in DEFAULT_TASKS}
    assert agents == {"minimal", "coding", "research", "critique"}


def test_summarize_counts_deterministic_and_judged():
    results = [
        EvalResult(task_id="a", agent="minimal", description="", passed=True, judge_score=None, judge_reason=None, output_preview=""),
        EvalResult(task_id="b", agent="minimal", description="", passed=False, judge_score=None, judge_reason=None, output_preview=""),
        EvalResult(task_id="c", agent="research", description="", passed=None, judge_score=4, judge_reason="ok", output_preview=""),
        EvalResult(task_id="d", agent="research", description="", passed=None, judge_score=2, judge_reason="meh", output_preview=""),
    ]
    summary = summarize(results)
    assert summary["total"] == 4
    assert summary["deterministic_total"] == 2
    assert summary["deterministic_passed"] == 1
    assert summary["judged_total"] == 2
    assert summary["average_judge_score"] == 3.0


def test_summarize_handles_empty_results():
    summary = summarize([])
    assert summary["total"] == 0
    assert summary["average_judge_score"] is None
