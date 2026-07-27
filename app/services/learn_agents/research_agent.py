"""Agent Lab, Phase 3: a prompted ReAct research agent.

Contrast this with Phase 1's minimal_agent: there, the *provider* parses
structured tool_calls out of the response for us. Here there is no such
structure — the model is instructed to write a Thought/Action/Observation
scratchpad in plain text, and *we* regex-parse it ourselves. That's the
core of "ReAct" (Yao et al., 2022): reasoning and acting interleaved in one
text stream, not two separate channels.

Loop:
    1. Ask the model to continue the scratchpad, stopping right after it
       writes an Action line (stop=["Observation:"] — we don't want it
       hallucinating its own observation).
    2. If the text contains "Final Answer:", we're done.
    3. Otherwise parse "Action: search[<query>]", run the search tool, and
       append "Observation: ..." as the next turn.
    4. If the model wrote neither, nudge it and try again.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.services.learn_agents._llm_client import chat_completion, extract_message
from app.services.learn_agents.tracing import RunTrace
from app.services.web_search import WebSearchService

MAX_STEPS = 6

SYSTEM_PROMPT = (
    "You answer questions by reasoning step by step and searching the web when you "
    "need current or factual information you're not sure of. Use exactly this format, "
    "one step per turn:\n\n"
    "Thought: <your reasoning about what to do next>\n"
    "Action: search[<search query>]\n\n"
    "You will then be given an Observation with search results. Keep alternating "
    "Thought/Action/Observation until you can answer. When you're ready, respond with:\n\n"
    "Thought: <final reasoning>\n"
    "Final Answer: <your answer to the user's question>\n\n"
    "Never write your own Observation — wait for it to be given to you. If the "
    "question needs no search, you may go straight to a Final Answer."
)

_ACTION_RE = re.compile(r"Action:\s*search\[(.+?)\]", re.IGNORECASE | re.DOTALL)
_FINAL_ANSWER_RE = re.compile(r"Final Answer:\s*(.+)", re.IGNORECASE | re.DOTALL)


def _format_results(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "No results found."
    lines = []
    for item in results[:5]:
        title = (item.get("title") or "").strip()
        body = (item.get("body") or "").strip()
        href = (item.get("href") or "").strip()
        lines.append(f"- {title}: {body} ({href})")
    return "\n".join(lines)


@dataclass
class ResearchAgentResult:
    answer: str
    steps: int
    scratchpad: str
    messages: List[Dict[str, Any]] = field(default_factory=list)


async def run_research_agent(
    *,
    query: str,
    settings: Settings,
    search_service: WebSearchService,
    trace: Optional[RunTrace] = None,
) -> ResearchAgentResult:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {query}"},
    ]
    scratchpad_parts: List[str] = []

    for step in range(1, MAX_STEPS + 1):
        if trace is not None:
            with trace.llm_call(request={"messages": messages, "stop": ["Observation:"]}) as recorder:
                payload, raw = await chat_completion(messages=messages, settings=settings, stop=["Observation:"])
                recorder.response = raw
        else:
            payload, raw = await chat_completion(messages=messages, settings=settings, stop=["Observation:"])

        assistant = extract_message(raw)
        text = str(assistant.get("content") or "").strip()
        scratchpad_parts.append(text)
        messages.append({"role": "assistant", "content": text})

        final_match = _FINAL_ANSWER_RE.search(text)
        if final_match:
            answer = final_match.group(1).strip()
            if trace is not None:
                trace.finish(answer=answer, steps=step)
            return ResearchAgentResult(
                answer=answer,
                steps=step,
                scratchpad="\n".join(scratchpad_parts),
                messages=messages,
            )

        action_match = _ACTION_RE.search(text)
        if action_match:
            search_query = action_match.group(1).strip()
            started = time.monotonic()
            results = await search_service.search(search_query)
            observation = _format_results(results)
            if trace is not None:
                trace.record_tool_call(
                    name="search",
                    arguments={"query": search_query},
                    result=observation,
                    duration_ms=(time.monotonic() - started) * 1000,
                )
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            continue

        # Model wrote neither an Action nor a Final Answer — nudge it.
        messages.append(
            {
                "role": "user",
                "content": "Please continue with either 'Action: search[...]' or 'Final Answer: ...'.",
            }
        )

    gave_up = f"(gave up after {MAX_STEPS} steps without a Final Answer — see scratchpad)"
    if trace is not None:
        trace.finish(answer=gave_up, steps=MAX_STEPS)
    return ResearchAgentResult(
        answer=gave_up,
        steps=MAX_STEPS,
        scratchpad="\n".join(scratchpad_parts),
        messages=messages,
    )


__all__ = ["run_research_agent", "ResearchAgentResult", "MAX_STEPS"]
