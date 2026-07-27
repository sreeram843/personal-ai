"""Agent Lab, Phase 6b: an eval harness so a prompt change can be measured.

A fixed set of tasks, each routed to one of the earlier lab agents. Tasks
with a deterministic, checkable answer (arithmetic, passing tests) are
scored exactly; open-ended tasks (research, critique) fall back to an
LLM-as-judge on a 1-5 scale. Re-run this after changing a prompt and compare
the summary instead of eyeballing a single transcript.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.services.learn_agents._llm_client import chat_completion, extract_message
from app.services.learn_agents.coding_agent import run_coding_agent
from app.services.learn_agents.critic_agent import run_critic_agent
from app.services.learn_agents.minimal_agent import run_minimal_agent
from app.services.learn_agents.research_agent import run_research_agent
from app.services.web_search import WebSearchService

JUDGE_SYSTEM_PROMPT = (
    "You grade an AI assistant's answer to a question. Score from 1 (unusable) to 5 "
    "(excellent) on whether the answer is correct, complete, and directly responsive. "
    "Reply in exactly this format:\nScore: <1-5>\nReason: <one sentence>"
)

_SCORE_RE = re.compile(r"Score:\s*(\d)")
_REASON_RE = re.compile(r"Reason:\s*(.+)", re.DOTALL)


@dataclass
class EvalTask:
    id: str
    agent: str  # "minimal" | "coding" | "research" | "critique"
    description: str
    input: Dict[str, Any]
    expects_substring: Optional[str] = None  # if set, deterministic pass/fail check


@dataclass
class EvalResult:
    task_id: str
    agent: str
    description: str
    passed: Optional[bool]  # deterministic outcome, or None if judged
    judge_score: Optional[int]
    judge_reason: Optional[str]
    output_preview: str


DEFAULT_TASKS: List[EvalTask] = [
    EvalTask(
        id="calc-1",
        agent="minimal",
        description="Basic arithmetic via the calculator tool",
        input={"query": "What is 12 * 7, then add 4?"},
        expects_substring="88",
    ),
    EvalTask(
        id="calc-2",
        agent="minimal",
        description="Order of operations",
        input={"query": "What is (100 - 40) / 3, rounded to the nearest whole number?"},
        expects_substring="20",
    ),
    EvalTask(
        id="code-1",
        agent="coding",
        description="Write a function that reverses a string",
        input={
            "spec": "Write a function `reverse_str(s: str) -> str` that returns the reversed string.",
            "tests": "assert reverse_str('abc') == 'cba'\nassert reverse_str('') == ''\nprint('ok')",
        },
    ),
    EvalTask(
        id="code-2",
        agent="coding",
        description="Write a function that sums values by category",
        input={
            "spec": (
                "Write a function `total_by_category(rows: list) -> dict` where rows is a "
                "list of dicts each with 'category' and 'amount' keys; return a dict mapping "
                "category to the sum of amounts."
            ),
            "tests": (
                "rows = [{'category': 'a', 'amount': 1}, {'category': 'b', 'amount': 2}, "
                "{'category': 'a', 'amount': 3}]\n"
                "assert total_by_category(rows) == {'a': 4, 'b': 2}\nprint('ok')"
            ),
        },
    ),
    EvalTask(
        id="research-1",
        agent="research",
        description="A question that needs a current-facts search",
        input={"query": "What year was the FastAPI web framework first released?"},
    ),
    EvalTask(
        id="critique-1",
        agent="critique",
        description="An open-ended question worth a drafter+critic pass",
        input={"query": "Explain what a race condition is, for a junior developer."},
    ),
]


async def _judge(*, question: str, answer: str, settings: Settings) -> tuple[Optional[int], Optional[str]]:
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}\n\nAnswer: {answer}"},
    ]
    _, raw = await chat_completion(messages=messages, settings=settings)
    text = str(extract_message(raw).get("content") or "")
    score_match = _SCORE_RE.search(text)
    score = int(score_match.group(1)) if score_match else None
    reason_match = _REASON_RE.search(text)
    reason = reason_match.group(1).strip() if reason_match else text.strip()[:200]
    return score, reason


async def run_eval_suite(
    *,
    settings: Settings,
    search_service: WebSearchService,
    tasks: Optional[List[EvalTask]] = None,
) -> List[EvalResult]:
    tasks = tasks if tasks is not None else DEFAULT_TASKS
    results: List[EvalResult] = []

    for task in tasks:
        if task.agent == "minimal":
            outcome = await run_minimal_agent(query=task.input["query"], settings=settings)
            answer = outcome.answer
        elif task.agent == "coding":
            outcome = await run_coding_agent(
                spec=task.input["spec"], tests=task.input["tests"], settings=settings
            )
            passed = outcome.passed
            results.append(
                EvalResult(
                    task_id=task.id,
                    agent=task.agent,
                    description=task.description,
                    passed=passed,
                    judge_score=None,
                    judge_reason=None,
                    output_preview=(outcome.code or outcome.output)[:300],
                )
            )
            continue
        elif task.agent == "research":
            outcome = await run_research_agent(
                query=task.input["query"], settings=settings, search_service=search_service
            )
            answer = outcome.answer
        elif task.agent == "critique":
            outcome = await run_critic_agent(query=task.input["query"], settings=settings)
            answer = outcome.final_answer
        else:
            results.append(
                EvalResult(
                    task_id=task.id,
                    agent=task.agent,
                    description=task.description,
                    passed=False,
                    judge_score=None,
                    judge_reason=f"unknown agent '{task.agent}'",
                    output_preview="",
                )
            )
            continue

        if task.expects_substring is not None:
            passed = task.expects_substring in answer
            results.append(
                EvalResult(
                    task_id=task.id,
                    agent=task.agent,
                    description=task.description,
                    passed=passed,
                    judge_score=None,
                    judge_reason=None,
                    output_preview=answer[:300],
                )
            )
            continue

        score, reason = await _judge(question=task.input.get("query", ""), answer=answer, settings=settings)
        results.append(
            EvalResult(
                task_id=task.id,
                agent=task.agent,
                description=task.description,
                passed=None,
                judge_score=score,
                judge_reason=reason,
                output_preview=answer[:300],
            )
        )

    return results


def summarize(results: List[EvalResult]) -> Dict[str, Any]:
    deterministic = [r for r in results if r.passed is not None]
    judged = [r for r in results if r.judge_score is not None]
    return {
        "total": len(results),
        "deterministic_passed": sum(1 for r in deterministic if r.passed),
        "deterministic_total": len(deterministic),
        "average_judge_score": (
            round(sum(r.judge_score for r in judged) / len(judged), 2) if judged else None
        ),
        "judged_total": len(judged),
    }


__all__ = [
    "EvalTask",
    "EvalResult",
    "DEFAULT_TASKS",
    "run_eval_suite",
    "summarize",
]
