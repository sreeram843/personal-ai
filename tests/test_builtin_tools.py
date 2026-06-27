"""Tests for built-in ToolRegistry bootstrap."""

from __future__ import annotations

import pytest

from app.services.builtin_tools import CHAT_AGENT_ROLE, register_builtin_tools
from app.services.tool_registry import ToolRegistry
from app.services.web_search import WebSearchService


@pytest.fixture
def registry_with_tools() -> ToolRegistry:
    registry = ToolRegistry()
    register_builtin_tools(registry, WebSearchService())
    return registry


def test_builtin_tools_register_once(registry_with_tools: ToolRegistry) -> None:
    count = len(registry_with_tools.list_tools_for_role(CHAT_AGENT_ROLE))
    register_builtin_tools(registry_with_tools, WebSearchService())
    assert len(registry_with_tools.list_tools_for_role(CHAT_AGENT_ROLE)) == count


def test_chat_agent_has_network_tools(registry_with_tools: ToolRegistry) -> None:
    tools = registry_with_tools.list_tools_for_role(CHAT_AGENT_ROLE)
    assert "fx_rate" in tools
    assert "market_price" in tools
    assert "get_crypto_price" in tools
    assert "get_game_score" in tools
    assert "weather" in tools
    assert "web_search" in tools
    assert "get_air_quality" in tools


def test_resolved_tool_query_accepts_query_or_user_query() -> None:
    from app.services.tool_invocation import resolved_tool_query

    assert resolved_tool_query(query="usd to inr") == "usd to inr"
    assert resolved_tool_query(user_query="weather in austin") == "weather in austin"
    assert resolved_tool_query(query="", user_query="latest ai news") == "latest ai news"
    assert resolved_tool_query() == ""
