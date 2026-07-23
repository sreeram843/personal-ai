#!/usr/bin/env python3
"""Smoke-test the CurAI agent loop with a mocked LLM (no Ollama required).

Usage (from repo root):
  python cli/scripts/smoke_generic_answer.py
  make cli-smoke
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Allow running without pip install -e .
CLI_ROOT = Path(__file__).resolve().parents[1]
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from curai.agent.loop import run_agent_sync
from curai.config import CliConfig, LlmConfig
from curai.llm.client import LlmResponse, ParsedToolCall

GENERIC_ANSWER = (
    "This is a generic smoke-test answer from the mocked LLM. "
    "The CurAI CLI agent loop completed successfully without calling external tools."
)

TOOL_THEN_ANSWER = [
    LlmResponse(
        content="",
        tool_calls=[
            ParsedToolCall(
                id="call_smoke_1",
                name="list_directory",
                arguments={"path": ".", "max_depth": 1},
            )
        ],
    ),
    LlmResponse(content=GENERIC_ANSWER),
]


async def _mock_generic(*_args, **_kwargs) -> LlmResponse:
    return LlmResponse(content=GENERIC_ANSWER)


async def _mock_with_tool(*_args, **_kwargs) -> LlmResponse:
    if not _mock_with_tool._calls:
        _mock_with_tool._calls = 0
    idx = min(_mock_with_tool._calls, len(TOOL_THEN_ANSWER) - 1)
    _mock_with_tool._calls += 1
    return TOOL_THEN_ANSWER[idx]


_mock_with_tool._calls = 0  # type: ignore[attr-defined]


def run_scenario(name: str, mock_fn) -> None:
    config = CliConfig(
        llm=LlmConfig(provider="ollama", model="mock"),
        permission_mode="auto",
        max_agent_steps=5,
    )
    workspace = CLI_ROOT

    with patch("curai.agent.loop.LlmClient") as client_cls:
        instance = client_cls.return_value
        instance.chat_with_tools = AsyncMock(side_effect=mock_fn)
        answer = run_agent_sync(
            prompt="Give me a generic hello for smoke testing.",
            workspace=workspace,
            config=config,
        )

    if GENERIC_ANSWER not in answer:
        raise AssertionError(f"{name}: expected generic answer, got: {answer!r}")
    print(f"  OK  {name}")


def main() -> int:
    print("CurAI CLI smoke test (mocked LLM, no Ollama)\n")
    try:
        run_scenario("direct answer (no tools)", _mock_generic)
        _mock_with_tool._calls = 0  # type: ignore[attr-defined]
        run_scenario("tool call then answer", _mock_with_tool)
    except Exception as exc:
        print(f"  FAIL {exc}", file=sys.stderr)
        return 1
    print("\nAll smoke scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
