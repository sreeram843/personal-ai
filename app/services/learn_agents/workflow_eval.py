"""Opt-in evals for production `/workflow_chat`, scored like the Phase 6 lab harness.

Lab `eval_harness.py` only drives learn-agents. This module posts the same
summarize() table against the production workflow path: HTTP `/workflow_chat`,
OrchestratedChatService, or an injected `run_one` stub for unit tests.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

from app.services.learn_agents.eval_harness import EvalResult, summarize

RunOneFn = Callable[[str], Awaitable[str]]
JudgeFn = Callable[[str, str], Awaitable[tuple[Optional[int], Optional[str]]]]

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
OPT_IN_HELP = """\
Workflow eval is opt-in because it calls live /workflow_chat (and optionally an LLM judge).

Run:
  RUN_EVAL_WORKFLOW=1 python -m app.services.learn_agents.workflow_eval

Optional env:
  WORKFLOW_EVAL_BASE_URL     default http://127.0.0.1:8000
  WORKFLOW_EVAL_AUTH_TOKEN   Bearer token if AUTH_DISABLED=false
  WORKFLOW_EVAL_TIMEOUT      HTTP timeout seconds (default 300)
"""


@dataclass
class WorkflowEvalTask:
    id: str
    description: str
    prompt: str
    expects_substring: Optional[str] = None


DEFAULT_WORKFLOW_TASKS: List[WorkflowEvalTask] = [
    WorkflowEvalTask(
        id="compare-frameworks",
        description="Compare two Python web frameworks for a small REST API",
        prompt=(
            "Compare FastAPI and Flask for a small internal REST API. "
            "Which should a Python team pick and why?"
        ),
        expects_substring="FastAPI",
    ),
    WorkflowEvalTask(
        id="analyze-cache",
        description="Analyze Redis vs in-process cache for a single instance",
        prompt=(
            "Analyze when Redis is worth it versus an in-process cache for a "
            "single-instance FastAPI app. Name the tradeoffs."
        ),
        expects_substring="Redis",
    ),
    WorkflowEvalTask(
        id="multi-hop-python",
        description="Multi-hop: Python 3.0 timing relative to Python 2.0",
        prompt=(
            "Python 3.0 shipped in 2008. How many years after Python 2.0 (released in 2000) "
            "was that, and what compatibility break did 3.0 introduce?"
        ),
        expects_substring="8",
    ),
    WorkflowEvalTask(
        id="compare-rag",
        description="Compare RAG with fine-tuning when knowledge changes weekly",
        prompt=(
            "Compare retrieval-augmented generation with fine-tuning when the knowledge "
            "base changes weekly. Which approach should we default to?"
        ),
        expects_substring="retrieval",
    ),
    WorkflowEvalTask(
        id="analyze-step-cap",
        description="Analyze why an agent loop needs a max-step cap",
        prompt=(
            "Analyze why an agent loop needs a max-step cap, using a research agent "
            "that can search the web as the example."
        ),
    ),
    WorkflowEvalTask(
        id="multi-hop-linux",
        description="Multi-hop: Linux kernel author and implementation language",
        prompt="Who created the Linux kernel, and what language is the kernel primarily written in?",
        expects_substring="Linus",
    ),
    WorkflowEvalTask(
        id="compare-workflow",
        description="Contrast one-shot completion with a planner/reviewer workflow",
        prompt=(
            "Contrast a single LLM call with a coordinator-planner plus drafter, reviewer, "
            "and writer workflow. When is the extra cost justified?"
        ),
    ),
    WorkflowEvalTask(
        id="analyze-web-search",
        description="Analyze quality vs hallucination when adding web search",
        prompt=(
            "A product can answer from ingested docs only, or also search the public web. "
            "Analyze the quality versus hallucination tradeoff of adding web search."
        ),
    ),
]


def _answer_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    message = getattr(payload, "message", None)
    if isinstance(message, str):
        return message
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("answer") or "")
    return str(payload or "")


def _make_http_runner(
    client: Any, *, base_url: str, auth_token: Optional[str]
) -> RunOneFn:
    headers: Dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    client_base = str(getattr(client, "base_url", "") or "").rstrip("/")
    url = "/workflow_chat" if client_base else f"{base_url.rstrip('/')}/workflow_chat"

    async def run_one(prompt: str) -> str:
        posted = client.post(url, json={"message": prompt}, headers=headers)
        response = await posted if inspect.isawaitable(posted) else posted
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        body = response.json()
        data = await body if inspect.isawaitable(body) else body
        return _answer_text(data)

    return run_one


def _make_service_runner(service: Any) -> RunOneFn:
    async def run_one(prompt: str) -> str:
        response = await service.run_mode(
            mode="workflow",
            query=prompt,
            system_prompt="You are a helpful assistant.",
            chat_history=[],
            conversation_id=None,
            user_id=None,
            top_k=4,
            score_threshold=None,
            options={},
            use_rag=False,
            include_trace=False,
            persist_memory=False,
            max_steps=6,
        )
        return _answer_text(response)

    return run_one


def _resolve_run_one(
    *,
    run_one: Optional[RunOneFn],
    client: Optional[Any],
    service: Optional[Any],
    base_url: str,
    auth_token: Optional[str],
) -> RunOneFn:
    provided = [run_one is not None, client is not None, service is not None]
    if sum(provided) != 1:
        raise ValueError("Provide exactly one of run_one, client, or service")
    if run_one is not None:
        return run_one
    if client is not None:
        return _make_http_runner(client, base_url=base_url, auth_token=auth_token)
    return _make_service_runner(service)


async def _default_judge(question: str, answer: str, settings: Any) -> tuple[Optional[int], Optional[str]]:
    from app.services.learn_agents.eval_harness import _judge

    return await _judge(question=question, answer=answer, settings=settings)


async def run_workflow_eval_suite(
    *,
    run_one: Optional[RunOneFn] = None,
    client: Optional[Any] = None,
    service: Optional[Any] = None,
    tasks: Optional[Sequence[WorkflowEvalTask]] = None,
    judge: Optional[JudgeFn] = None,
    settings: Optional[Any] = None,
    base_url: str = DEFAULT_BASE_URL,
    auth_token: Optional[str] = None,
) -> List[EvalResult]:
    """Run workflow-shaped prompts and return EvalResult rows for summarize()."""
    runner = _resolve_run_one(
        run_one=run_one,
        client=client,
        service=service,
        base_url=base_url,
        auth_token=auth_token,
    )
    selected = list(tasks) if tasks is not None else list(DEFAULT_WORKFLOW_TASKS)
    score = judge
    if score is None and settings is not None:
        async def score(question: str, answer: str) -> tuple[Optional[int], Optional[str]]:
            return await _default_judge(question, answer, settings)

    results: List[EvalResult] = []
    for task in selected:
        answer = await runner(task.prompt)
        preview = answer[:300]
        if task.expects_substring is not None:
            results.append(
                EvalResult(
                    task_id=task.id,
                    agent="workflow",
                    description=task.description,
                    passed=task.expects_substring in answer,
                    judge_score=None,
                    judge_reason=None,
                    output_preview=preview,
                )
            )
            continue
        if score is None:
            results.append(
                EvalResult(
                    task_id=task.id,
                    agent="workflow",
                    description=task.description,
                    passed=None,
                    judge_score=None,
                    judge_reason=None,
                    output_preview=preview,
                )
            )
            continue
        judge_score, judge_reason = await score(task.prompt, answer)
        results.append(
            EvalResult(
                task_id=task.id,
                agent="workflow",
                description=task.description,
                passed=None,
                judge_score=judge_score,
                judge_reason=judge_reason,
                output_preview=preview,
            )
        )
    return results


def _print_table(results: List[EvalResult]) -> None:
    table = summarize(results)
    table["results"] = [
        {
            "task_id": row.task_id,
            "passed": row.passed,
            "judge_score": row.judge_score,
            "judge_reason": row.judge_reason,
            "output_preview": row.output_preview,
        }
        for row in results
    ]
    print(json.dumps(table, indent=2))


async def _live_main() -> int:
    import httpx

    from app.core.config import get_settings

    base_url = os.environ.get("WORKFLOW_EVAL_BASE_URL", DEFAULT_BASE_URL)
    auth_token = os.environ.get("WORKFLOW_EVAL_AUTH_TOKEN") or os.environ.get("AUTH_TOKEN")
    timeout = float(os.environ.get("WORKFLOW_EVAL_TIMEOUT", "300"))
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        results = await run_workflow_eval_suite(
            client=client,
            settings=get_settings(),
            auth_token=auth_token,
        )
    _print_table(results)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    del argv
    if os.environ.get("RUN_EVAL_WORKFLOW") != "1":
        print(OPT_IN_HELP)
        return 0
    try:
        return asyncio.run(_live_main())
    except Exception as exc:  # noqa: BLE001 — CLI must surface live failures
        print(f"Workflow eval failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "WorkflowEvalTask",
    "DEFAULT_WORKFLOW_TASKS",
    "run_workflow_eval_suite",
    "summarize",
    "main",
]
