"""Tests for native ToolRegistry-backed tool agent."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.schemas.tool import ToolCapability, ToolRiskClass, ToolSpec
from app.services.tool_agent import build_openai_tool_definitions, run_tool_agent
from app.services.tool_registry import ToolRegistry


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()

    async def search_executor(inputs: dict, timeout: float) -> str:
        query = inputs.get("query") or inputs.get("user_query") or ""
        return f"search-results-for:{query}"

    reg.register_tool(
        ToolSpec(
            tool_id="web_search",
            name="Web Search",
            description="Search the public web.",
            risk_class=ToolRiskClass.NETWORK,
            capabilities={ToolCapability.NETWORK_REQUEST},
            allowed_roles={"chat_agent"},
        ),
        search_executor,
    )
    return reg


def test_build_openai_tool_definitions(registry: ToolRegistry) -> None:
    tools = build_openai_tool_definitions(registry, role="chat_agent")
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "web_search"
    assert tools[0]["function"]["parameters"]["type"] == "object"


def test_run_tool_agent_single_turn(registry: ToolRegistry) -> None:
    settings = Settings(
        llm_default_provider="openai",
        llm_openai_base_url="https://example.com",
        llm_default_model="test-model",
    )

    first_response = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": json.dumps({"query": "Dune plot"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    second_response = {
        "choices": [
            {
                "message": {
                    "content": "Dune is about Paul Atreides.",
                    "tool_calls": [],
                }
            }
        ]
    }

    mock_post = AsyncMock(side_effect=[_mock_http_response(first_response), _mock_http_response(second_response)])

    async def _run() -> str:
        with patch("app.services.tool_agent.httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.post = mock_post
            return await run_tool_agent(
                query="Summarize Dune",
                system_prompt="You are helpful.",
                chat_history=[],
                tool_registry=registry,
                settings=settings,
            )

    text = asyncio.run(_run())
    assert text == "Dune is about Paul Atreides."
    assert mock_post.await_count == 2
    tool_message = mock_post.await_args_list[1].kwargs["json"]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert "search-results-for:Dune plot" in tool_message["content"]


def test_run_tool_agent_ollama_response_shape(registry: ToolRegistry) -> None:
    settings = Settings(llm_default_provider="ollama", ollama_chat_model="llama3.1")

    payload = {
        "message": {
            "content": "Hello without tools.",
            "tool_calls": [],
        }
    }
    mock_post = AsyncMock(return_value=_mock_http_response(payload))

    async def _run() -> str:
        with patch("app.services.tool_agent.httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.post = mock_post
            return await run_tool_agent(
                query="hi",
                system_prompt="system",
                chat_history=[],
                tool_registry=registry,
                settings=settings,
            )

    text = asyncio.run(_run())
    assert text == "Hello without tools."
    assert "/api/chat" in mock_post.await_args.args[0]


def _mock_http_response(payload: dict) -> object:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    return _Response()
