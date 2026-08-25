"""Tests for production workflow eval (pure functions + stubbed runner)."""

from __future__ import annotations

import asyncio

from app.services.learn_agents.eval_harness import EvalResult, summarize
from app.services.learn_agents.workflow_eval import (
    DEFAULT_WORKFLOW_TASKS,
    main,
    run_workflow_eval_suite,
)


def test_default_workflow_tasks_have_unique_ids():
    ids = [task.id for task in DEFAULT_WORKFLOW_TASKS]
    assert len(ids) == len(set(ids))
    assert 6 <= len(DEFAULT_WORKFLOW_TASKS) <= 8


def test_summarize_counts_deterministic_and_judged():
    results = [
        EvalResult(
            task_id="a",
            agent="workflow",
            description="",
            passed=True,
            judge_score=None,
            judge_reason=None,
            output_preview="",
        ),
        EvalResult(
            task_id="b",
            agent="workflow",
            description="",
            passed=False,
            judge_score=None,
            judge_reason=None,
            output_preview="",
        ),
        EvalResult(
            task_id="c",
            agent="workflow",
            description="",
            passed=None,
            judge_score=4,
            judge_reason="ok",
            output_preview="",
        ),
        EvalResult(
            task_id="d",
            agent="workflow",
            description="",
            passed=None,
            judge_score=2,
            judge_reason="meh",
            output_preview="",
        ),
    ]
    summary = summarize(results)
    assert summary["total"] == 4
    assert summary["deterministic_total"] == 2
    assert summary["deterministic_passed"] == 1
    assert summary["judged_total"] == 2
    assert summary["average_judge_score"] == 3.0


def test_stubbed_runner_produces_results_table():
    async def run_one(prompt: str) -> str:
        return (
            "FastAPI is the better default for typed REST APIs. Redis helps when "
            "you outgrow a process cache. Python 3.0 came 8 years after 2.0. "
            "Weekly-changing knowledge should use retrieval, not fine-tuning. "
            "Linus Torvalds wrote the Linux kernel in C."
        )

    results = asyncio.run(run_workflow_eval_suite(run_one=run_one))
    table = summarize(results)
    assert table["total"] == len(DEFAULT_WORKFLOW_TASKS)
    deterministic = [task for task in DEFAULT_WORKFLOW_TASKS if task.expects_substring]
    assert table["deterministic_total"] == len(deterministic)
    assert table["deterministic_passed"] == len(deterministic)
    assert table["judged_total"] == 0
    assert table["average_judge_score"] is None
    assert {row.task_id for row in results} == {task.id for task in DEFAULT_WORKFLOW_TASKS}
    assert all(row.agent == "workflow" for row in results)


def test_stubbed_runner_fails_missing_substring():
    async def run_one(prompt: str) -> str:
        return "No framework names here."

    results = asyncio.run(run_workflow_eval_suite(run_one=run_one))
    table = summarize(results)
    assert table["deterministic_passed"] == 0
    assert table["deterministic_total"] > 0


def test_cli_prints_opt_in_instructions(monkeypatch, capsys):
    monkeypatch.delenv("RUN_EVAL_WORKFLOW", raising=False)
    assert main() == 0
    out = capsys.readouterr().out
    assert "RUN_EVAL_WORKFLOW=1" in out
    assert "python -m app.services.learn_agents.workflow_eval" in out
