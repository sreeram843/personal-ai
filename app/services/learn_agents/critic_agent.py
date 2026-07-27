"""Agent Lab, Phase 5: a two-agent drafter + critic pair.

This is the smallest possible multi-agent system: one LLM call drafts an
answer, a second LLM call (with a different system prompt — the only thing
that makes it a "different agent") scores the draft against a rubric and
gives concrete feedback, and the first call revises once. Compare this
against a single-pass answer to the same question and judge for yourself
whether the extra round-trip earned its cost in latency and tokens — that
judgment call is the actual lesson of this phase, not the code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.services.learn_agents._llm_client import chat_completion, extract_message
from app.services.learn_agents.tracing import RunTrace

DRAFTER_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question directly and completely "
    "in a few sentences."
)

CRITIC_SYSTEM_PROMPT = (
    "You are a critical reviewer. You will be given a question and a draft answer. "
    "Score the draft from 1-10 on each of: Completeness, Clarity, and Directness "
    "(does it actually answer the question, or hedge/ramble). Then give 2-4 concrete, "
    "actionable pieces of feedback for revision. Reply in exactly this format:\n\n"
    "Completeness: <score>/10\n"
    "Clarity: <score>/10\n"
    "Directness: <score>/10\n"
    "Feedback:\n"
    "- <point>\n"
    "- <point>"
)

_SCORE_RE = re.compile(r"(Completeness|Clarity|Directness):\s*(\d+)\s*/\s*10", re.IGNORECASE)


def _parse_scores(critique_text: str) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for name, value in _SCORE_RE.findall(critique_text):
        scores[name.capitalize()] = int(value)
    return scores


@dataclass
class CritiqueResult:
    draft: str
    critique: str
    scores: Dict[str, int]
    final_answer: str
    steps: int
    messages: List[Dict[str, Any]] = field(default_factory=list)


async def _call(
    *, messages: List[Dict[str, Any]], settings: Settings, trace: Optional[RunTrace], label: str
) -> str:
    if trace is not None:
        with trace.llm_call(request={"label": label, "messages": messages}) as recorder:
            _, raw = await chat_completion(messages=messages, settings=settings)
            recorder.response = raw
    else:
        _, raw = await chat_completion(messages=messages, settings=settings)
    return str(extract_message(raw).get("content") or "").strip()


async def run_critic_agent(
    *, query: str, settings: Settings, trace: Optional[RunTrace] = None
) -> CritiqueResult:
    # Step 1: drafter produces an initial answer.
    draft_messages = [
        {"role": "system", "content": DRAFTER_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    draft = await _call(messages=draft_messages, settings=settings, trace=trace, label="draft")
    if trace is not None:
        trace.note("drafter produced initial answer")

    # Step 2: critic scores the draft and gives feedback.
    critic_messages = [
        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {query}\n\nDraft answer:\n{draft}"},
    ]
    critique = await _call(messages=critic_messages, settings=settings, trace=trace, label="critique")
    scores = _parse_scores(critique)
    if trace is not None:
        trace.record_tool_call(
            name="critic_scores", arguments={}, result=scores, duration_ms=0.0
        )

    # Step 3: drafter revises once, given the critique.
    revise_messages = draft_messages + [
        {"role": "assistant", "content": draft},
        {
            "role": "user",
            "content": (
                f"Here is feedback on your draft:\n{critique}\n\n"
                "Revise your answer to address it. Reply with only the revised answer."
            ),
        },
    ]
    final_answer = await _call(
        messages=revise_messages, settings=settings, trace=trace, label="revise"
    )

    if trace is not None:
        trace.finish(answer=final_answer, steps=3)

    return CritiqueResult(
        draft=draft,
        critique=critique,
        scores=scores,
        final_answer=final_answer,
        steps=3,
        messages=revise_messages + [{"role": "assistant", "content": final_answer}],
    )


__all__ = ["run_critic_agent", "CritiqueResult"]
