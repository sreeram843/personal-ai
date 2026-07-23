from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from curai.agent.loop import run_agent_sync
from curai.config import CliConfig, LlmConfig
from curai.llm.client import LlmResponse

GENERIC = "Generic mocked answer for pytest."


async def _mock_llm(*_args, **_kwargs) -> LlmResponse:
    return LlmResponse(content=GENERIC)


def test_agent_returns_mocked_generic_answer(tmp_path: Path) -> None:
    config = CliConfig(llm=LlmConfig(model="mock"), permission_mode="auto", max_agent_steps=3)
    with patch("curai.agent.loop.LlmClient") as client_cls:
        client_cls.return_value.chat_with_tools = AsyncMock(side_effect=_mock_llm)
        answer = run_agent_sync(
            prompt="Say something generic.",
            workspace=tmp_path,
            config=config,
        )
    assert GENERIC in answer
