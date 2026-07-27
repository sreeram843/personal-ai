"""Agent Lab, Phase 1: the smallest possible tool-calling agent.

This module is deliberately self-contained — no ToolRegistry, no framework,
no shared helpers — so the whole agentic loop fits on one screen:

    1. Send the LLM the conversation so far plus a list of tool definitions.
    2. If the reply contains tool_calls, run each tool and append the results
       to the conversation as role="tool" messages.
    3. Go back to 1. Stop when the LLM replies with plain text (the answer)
       or the step cap is hit.

Every request payload and raw response is captured in the returned transcript
so you can read exactly what went over the wire. Compare with the production
loop in app/services/tool_agent.py once this one makes sense.
"""

from __future__ import annotations

import ast
import json
import operator
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import Settings
from app.services.learn_agents.tracing import RunTrace

# The cap exists because a confused model can call tools forever — e.g. it
# keeps "checking" the same result or never emits a plain-text answer.
MAX_STEPS = 5

SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the calculate tool for any arithmetic "
    "instead of computing it yourself. When you have the answer, reply in "
    "plain text without calling more tools."
)

# --- The one tool: a safe arithmetic calculator -----------------------------

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 64:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression (AST-walked, so no eval/exec risk)."""
    if len(expression) > 200:
        return "ERROR: expression too long"
    try:
        return str(_eval_node(ast.parse(expression, mode="eval")))
    except Exception as exc:  # surfaced to the model as a tool result
        return f"ERROR: {exc}"


# This JSON schema is what the LLM actually "sees" — the model never touches
# the Python function, only this description of it.
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate an arithmetic expression, e.g. '(2 + 3) * 4 / 5'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The arithmetic expression to evaluate.",
                    }
                },
                "required": ["expression"],
            },
        },
    }
]


# --- The loop ---------------------------------------------------------------


@dataclass
class MinimalAgentResult:
    answer: str
    steps: int
    # One entry per LLM round-trip: {"step", "request", "response"} with the
    # exact JSON payloads. Read these to learn the wire format.
    events: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)


def _endpoint(settings: Settings) -> tuple[str, Dict[str, str], Dict[str, Any], float]:
    """Return (url, headers, base_payload, timeout) for the configured LLM."""
    if settings.llm_default_provider == "openai" and settings.llm_openai_base_url:
        base = settings.llm_openai_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        headers = {"Content-Type": "application/json"}
        if settings.llm_openai_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_openai_api_key}"
        payload = {"model": settings.llm_default_model, "temperature": 0}
        return f"{base}/chat/completions", headers, payload, settings.llm_openai_timeout
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {"model": settings.ollama_chat_model, "stream": False}
    return url, {"Content-Type": "application/json"}, payload, 120.0


def _extract_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the assistant message from OpenAI-style or Ollama responses."""
    if raw.get("choices"):
        return raw["choices"][0].get("message") or {}
    return raw.get("message") or {}


async def run_minimal_agent(
    *, query: str, settings: Settings, trace: Optional[RunTrace] = None
) -> MinimalAgentResult:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    url, headers, base_payload, timeout = _endpoint(settings)
    events: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for step in range(1, MAX_STEPS + 1):
            payload = {**base_payload, "messages": messages, "tools": TOOL_DEFINITIONS}
            if trace is not None:
                with trace.llm_call(request=payload) as recorder:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    raw = response.json()
                    recorder.response = raw
            else:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                raw = response.json()
            events.append({"step": step, "request": payload, "response": raw})

            assistant = _extract_message(raw)
            tool_calls = assistant.get("tool_calls") or []

            if not tool_calls:
                answer = str(assistant.get("content") or "").strip()
                if trace is not None:
                    trace.finish(answer=answer or "(model returned no output)", steps=step)
                return MinimalAgentResult(
                    answer=answer or "(model returned no output)",
                    steps=step,
                    events=events,
                    messages=messages + [assistant],
                )

            # Echo the assistant's tool-call message back into the history —
            # the model needs to see its own request next to the results.
            messages.append(assistant)

            for index, call in enumerate(tool_calls):
                fn = call.get("function") or {}
                args = fn.get("arguments") or {}
                if isinstance(args, str):  # OpenAI sends arguments as a JSON string
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                call_started = time.monotonic()
                if fn.get("name") == "calculate":
                    output = calculate(str(args.get("expression", "")))
                else:
                    output = f"ERROR: unknown tool '{fn.get('name')}'"
                if trace is not None:
                    trace.record_tool_call(
                        name=str(fn.get("name") or "unknown"),
                        arguments=args,
                        result=output,
                        duration_ms=(time.monotonic() - call_started) * 1000,
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id") or f"call_{step}_{index}"),
                        "content": output,
                    }
                )

    gave_up = f"(gave up after {MAX_STEPS} steps — see transcript)"
    if trace is not None:
        trace.finish(answer=gave_up, steps=MAX_STEPS)
    return MinimalAgentResult(
        answer=gave_up,
        steps=MAX_STEPS,
        events=events,
        messages=messages,
    )


__all__ = ["run_minimal_agent", "MinimalAgentResult", "calculate", "MAX_STEPS"]
