"""Agent Lab, Phase 7 (optional): a tool-building agent.

Given a natural-language description, this agent writes a small Python
function using the same write/run/fix loop as Phase 4's coding agent
(reused directly — this phase adds nothing new to *how* code gets vetted),
then answers one query with it: the model picks the call arguments, and the
already-vetted function runs in a subprocess with them.

This is where dynamic capability meets the reason permissions and sandboxing
exist in the production app (see app/services/sandbox_policy.py and
app/services/tool_permissions.py): the model is choosing what code to run
based on its own reading of a natural-language spec, so nothing here
executes without the Phase 4 safety check passing first, and it's checked
again immediately before the call that actually uses user-supplied
arguments.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import Settings
from app.services.learn_agents._code_safety import check_code_safety
from app.services.learn_agents._llm_client import chat_completion, extract_message
from app.services.learn_agents.coding_agent import EXEC_TIMEOUT_SECONDS, run_coding_agent
from app.services.learn_agents.tracing import RunTrace

ARG_SYSTEM_PROMPT_TEMPLATE = (
    "You have access to exactly one tool, `{name}`, described as: {description}\n"
    "It takes these parameters: {signature}\n"
    'Given the user\'s question, reply with ONLY a JSON object of the arguments to call '
    'it with, e.g. {{"word": "banana"}}. No explanation, no code fence.'
)

_DEF_RE = re.compile(r"def\s+(\w+)\s*\((.*?)\)", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _signature_of(code: str) -> tuple[Optional[str], str]:
    match = _DEF_RE.search(code)
    if not match:
        return None, ""
    return match.group(1), match.group(2).strip()


def _run_tool_call(code: str, func_name: str, arguments: Dict[str, Any]) -> tuple[bool, str]:
    """Execute the vetted function with the given arguments in a subprocess."""
    call_script = (
        f"{code}\n\n"
        f"import json\n"
        f"_args = json.loads({json.dumps(json.dumps(arguments))})\n"
        f"print(json.dumps({func_name}(**_args)))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "tool_call.py"
        script_path.write_text(call_script)
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
            return True, result.stdout.strip()
        return False, (result.stderr or result.stdout or "unknown failure").strip()[-2000:]


@dataclass
class ToolBuilderResult:
    tool_name: Optional[str]
    tool_code: str
    build_passed: bool
    build_output: str
    answer: str
    steps: int


async def run_tool_builder_agent(
    *,
    tool_description: str,
    build_tests: str,
    query: str,
    settings: Settings,
    trace: Optional[RunTrace] = None,
) -> ToolBuilderResult:
    # Phase A: write + vet the tool, reusing the Phase 4 write/run/fix loop verbatim.
    build = await run_coding_agent(
        spec=tool_description, tests=build_tests, settings=settings, trace=trace
    )
    if not build.passed:
        if trace is not None:
            trace.fail(error="tool failed to pass its own build tests", steps=build.steps)
        return ToolBuilderResult(
            tool_name=None,
            tool_code=build.code,
            build_passed=False,
            build_output=build.output,
            answer="(tool was never built successfully — see build_output)",
            steps=build.steps,
        )

    func_name, signature = _signature_of(build.code)
    if not func_name:
        return ToolBuilderResult(
            tool_name=None,
            tool_code=build.code,
            build_passed=True,
            build_output=build.output,
            answer="(built code has no recognizable function definition)",
            steps=build.steps,
        )

    # Phase B: ask the model to pick arguments for the new tool given the user's query.
    arg_messages = [
        {
            "role": "system",
            "content": ARG_SYSTEM_PROMPT_TEMPLATE.format(
                name=func_name, description=tool_description, signature=signature
            ),
        },
        {"role": "user", "content": query},
    ]
    if trace is not None:
        with trace.llm_call(request={"messages": arg_messages}) as recorder:
            _, raw = await chat_completion(messages=arg_messages, settings=settings)
            recorder.response = raw
    else:
        _, raw = await chat_completion(messages=arg_messages, settings=settings)

    text = str(extract_message(raw).get("content") or "")
    json_match = _JSON_OBJECT_RE.search(text)
    try:
        arguments = json.loads(json_match.group(0)) if json_match else {}
    except json.JSONDecodeError:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}

    # Re-check safety immediately before the call that uses model-chosen arguments —
    # cheap, and it's the last gate before this code actually runs against real input.
    safety_error = check_code_safety(build.code)
    if safety_error:
        if trace is not None:
            trace.fail(error=f"safety re-check failed: {safety_error}", steps=build.steps + 1)
        return ToolBuilderResult(
            tool_name=func_name,
            tool_code=build.code,
            build_passed=True,
            build_output=build.output,
            answer=f"REJECTED before call: {safety_error}",
            steps=build.steps + 1,
        )

    started = time.monotonic()
    ok, output = _run_tool_call(build.code, func_name, arguments)
    if trace is not None:
        trace.record_tool_call(
            name=func_name,
            arguments=arguments,
            result=output,
            duration_ms=(time.monotonic() - started) * 1000,
        )
        trace.finish(answer=output if ok else f"ERROR: {output}", steps=build.steps + 1)

    return ToolBuilderResult(
        tool_name=func_name,
        tool_code=build.code,
        build_passed=True,
        build_output=build.output,
        answer=output if ok else f"ERROR calling {func_name}: {output}",
        steps=build.steps + 1,
    )


__all__ = ["run_tool_builder_agent", "ToolBuilderResult"]
