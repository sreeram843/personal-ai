"""Agent Lab, Phase 4: write -> run -> read the traceback -> fix -> repeat.

Unlike the research agent, success here is unambiguous: the generated
function either passes the given tests or it doesn't. That makes this the
clearest place to *watch* an agent self-correct — each failed attempt's
stderr becomes the next turn's observation, verbatim.

Generated code is never trusted: it's statically checked (see
_code_safety.py) and then run as a short-lived subprocess with a hard
timeout, never in-process.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.services.learn_agents._code_safety import check_code_safety
from app.services.learn_agents._llm_client import chat_completion, extract_message
from app.services.learn_agents.tracing import RunTrace

MAX_STEPS = 5
EXEC_TIMEOUT_SECONDS = 5

SYSTEM_PROMPT = (
    "You write small, correct Python functions. Reply with ONLY a single fenced "
    "python code block containing the function definition and any helpers it "
    "needs — no explanation text, no imports beyond the standard library's "
    "pure-computation modules (math, collections, itertools, re, json, string). "
    "If you are given a failing test observation, fix the function and reply "
    "again with the FULL corrected code block (not a diff)."
)

_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _extract_code(text: str) -> Optional[str]:
    match = _CODE_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    stripped = text.strip()
    return stripped or None


def _run_in_subprocess(code: str, tests: str) -> tuple[bool, str]:
    """Run candidate code + tests as a standalone script; return (passed, output)."""
    with tempfile.TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "candidate.py"
        script_path.write_text(f"{code}\n\n{tests}\n")
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return False, f"TIMEOUT: execution exceeded {EXEC_TIMEOUT_SECONDS}s"
        if result.returncode == 0:
            return True, result.stdout or "(no output; tests passed silently)"
        return False, (result.stderr or result.stdout or "unknown failure").strip()[-4000:]


@dataclass
class CodingAgentResult:
    passed: bool
    code: str
    steps: int
    output: str
    attempts: List[Dict[str, Any]] = field(default_factory=list)


async def run_coding_agent(
    *,
    spec: str,
    tests: str,
    settings: Settings,
    trace: Optional[RunTrace] = None,
) -> CodingAgentResult:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Spec:\n{spec}\n\n"
                f"Your code will have this test script appended below it and executed:\n"
                f"```python\n{tests}\n```"
            ),
        },
    ]
    attempts: List[Dict[str, Any]] = []
    last_code = ""

    for step in range(1, MAX_STEPS + 1):
        if trace is not None:
            with trace.llm_call(request={"messages": messages}) as recorder:
                _, raw = await chat_completion(messages=messages, settings=settings)
                recorder.response = raw
        else:
            _, raw = await chat_completion(messages=messages, settings=settings)

        assistant = extract_message(raw)
        text = str(assistant.get("content") or "")
        messages.append({"role": "assistant", "content": text})

        code = _extract_code(text)
        if not code:
            attempts.append({"step": step, "code": None, "passed": False, "output": "no code block found"})
            messages.append({"role": "user", "content": "Please reply with a single fenced python code block."})
            continue

        last_code = code
        safety_error = check_code_safety(code)
        if safety_error:
            observation = f"REJECTED before execution: {safety_error}"
            attempts.append({"step": step, "code": code, "passed": False, "output": observation})
            if trace is not None:
                trace.record_tool_call(
                    name="safety_check", arguments={}, result=observation, duration_ms=0.0
                )
            messages.append({"role": "user", "content": f"Observation: {observation}\nRevise the code."})
            continue

        started = time.monotonic()
        passed, output = _run_in_subprocess(code, tests)
        duration_ms = (time.monotonic() - started) * 1000
        attempts.append({"step": step, "code": code, "passed": passed, "output": output})
        if trace is not None:
            trace.record_tool_call(
                name="execute",
                arguments={"code_length": len(code)},
                result={"passed": passed, "output": output},
                duration_ms=duration_ms,
            )

        if passed:
            if trace is not None:
                trace.finish(answer=code, steps=step)
            return CodingAgentResult(passed=True, code=code, steps=step, output=output, attempts=attempts)

        messages.append(
            {"role": "user", "content": f"Observation: tests failed.\n{output}\nFix the code and reply again."}
        )

    if trace is not None:
        trace.fail(error="gave up without passing tests", steps=MAX_STEPS)
    return CodingAgentResult(
        passed=False,
        code=last_code,
        steps=MAX_STEPS,
        output="gave up after max steps without passing tests",
        attempts=attempts,
    )


__all__ = ["run_coding_agent", "CodingAgentResult", "MAX_STEPS", "EXEC_TIMEOUT_SECONDS"]
