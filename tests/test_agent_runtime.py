"""Tests for tool permission modes and MCP store."""

import asyncio

import pytest

from app.schemas.agent import ChatAgentOptions
from app.schemas.tool import ToolCapability, ToolInvocationRequest, ToolRiskClass, ToolSpec
from app.services.mcp_store import build_mcp_server_store
from app.services.tool_permissions import (
    activate_tool_execution_context,
    deactivate_tool_execution_context,
    evaluate_tool_permission,
    get_tool_execution_context,
)
from app.services.tool_registry import ToolRegistry


def test_mcp_store_crud(tmp_path) -> None:
    store = build_mcp_server_store(file_path=str(tmp_path / "mcp.json"))
    created = store.create(
        user_id="user-1",
        name="GitHub",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer test"},
    )
    assert created.id
    listed = store.list_for_user("user-1")
    assert len(listed) == 1
    assert listed[0].name == "GitHub"
    store.record_status(created.id, user_id="user-1", status="connected", tool_count=3)
    refreshed = store.get(created.id, user_id="user-1")
    assert refreshed is not None
    assert refreshed.tool_count == 3
    assert store.delete(created.id, user_id="user-1")
    assert store.list_for_user("user-1") == []


def test_chat_agent_options_from_request() -> None:
    opts = ChatAgentOptions.from_request_options(
        {"tool_permission_mode": "plan", "approved_tool_ids": ["mcp_abc_search"]}
    )
    assert opts.tool_permission_mode == "plan"
    assert opts.approved_tool_ids == ["mcp_abc_search"]


def test_plan_mode_records_planned_tools_without_execution() -> None:
    async def _run() -> None:
        spec = ToolSpec(
            tool_id="mcp_srv_create_issue",
            name="Create Issue",
            description="Creates a GitHub issue",
            risk_class=ToolRiskClass.NETWORK,
            capabilities={ToolCapability.NETWORK_REQUEST},
            allowed_roles={"chat_agent"},
            requires_approval=True,
        )
        options = ChatAgentOptions(tool_permission_mode="plan")
        token = activate_tool_execution_context(options, user_id="user-1")
        ctx = get_tool_execution_context()
        assert ctx is not None
        action, approved_by = evaluate_tool_permission(
            "mcp_srv_create_issue",
            spec,
            inputs={"title": "Bug"},
            ctx=ctx,
        )
        assert action == "plan_only"
        assert approved_by is None
        assert len(ctx.planned) == 1
        deactivate_tool_execution_context(token)

    asyncio.run(_run())


def test_ask_mode_requires_approval_for_mcp_write_tools() -> None:
    async def _run() -> None:
        spec = ToolSpec(
            tool_id="mcp_srv_create_issue",
            name="Create Issue",
            description="Creates a GitHub issue",
            risk_class=ToolRiskClass.NETWORK,
            allowed_roles={"chat_agent"},
        )
        token = activate_tool_execution_context(
            ChatAgentOptions(tool_permission_mode="ask"),
            user_id="user-1",
        )
        ctx = get_tool_execution_context()
        assert ctx is not None
        action, _ = evaluate_tool_permission(
            "mcp_srv_create_issue",
            spec,
            inputs={"title": "Bug"},
            ctx=ctx,
        )
        assert action == "needs_approval"
        assert len(ctx.pending_approvals) == 1
        deactivate_tool_execution_context(token)

    asyncio.run(_run())


def test_auto_mode_passes_approval_for_network_tools() -> None:
    async def _run() -> None:
        spec = ToolSpec(
            tool_id="mcp_srv_list_repos",
            name="List Repos",
            description="Lists repositories",
            risk_class=ToolRiskClass.NETWORK,
            allowed_roles={"chat_agent"},
            requires_approval=True,
        )
        token = activate_tool_execution_context(
            ChatAgentOptions(tool_permission_mode="auto"),
            user_id="user-42",
        )
        ctx = get_tool_execution_context()
        assert ctx is not None
        action, approved_by = evaluate_tool_permission(
            "mcp_srv_list_repos",
            spec,
            inputs={},
            ctx=ctx,
        )
        assert action == "execute"
        assert approved_by == "auto:user-42"
        deactivate_tool_execution_context(token)

    asyncio.run(_run())


def test_tool_registry_session_overlay() -> None:
    registry = ToolRegistry()
    base = ToolSpec(
        tool_id="weather",
        name="Weather",
        description="Weather lookup",
        risk_class=ToolRiskClass.SAFE,
        allowed_roles={"chat_agent"},
    )

    async def base_exec(inputs, timeout):
        return "sunny"

    registry.register_tool(base, base_exec)
    session_spec = ToolSpec(
        tool_id="mcp_test_tool",
        name="MCP Tool",
        description="Remote tool",
        risk_class=ToolRiskClass.NETWORK,
        allowed_roles={"chat_agent"},
    )

    async def session_exec(inputs, timeout):
        return "remote"

    token = registry.activate_session_tools({"mcp_test_tool": (session_spec, session_exec)})
    tools = registry.list_tools_for_role("chat_agent")
    assert "weather" in tools
    assert "mcp_test_tool" in tools
    registry.deactivate_session_tools(token)
    assert "mcp_test_tool" not in registry.list_tools_for_role("chat_agent")


def test_tool_registry_session_overlay_invoke() -> None:
    async def _run() -> None:
        registry = ToolRegistry()
        spec = ToolSpec(
            tool_id="mcp_only",
            name="MCP",
            description="",
            risk_class=ToolRiskClass.SAFE,
            allowed_roles={"chat_agent"},
        )

        async def session_exec(inputs, timeout):
            return "mcp-result"

        token = registry.activate_session_tools({"mcp_only": (spec, session_exec)})
        result = await registry.invoke_tool(
            ToolInvocationRequest(tool_id="mcp_only", role="chat_agent", inputs={})
        )
        assert result.success
        assert result.output == "mcp-result"
        registry.deactivate_session_tools(token)

    asyncio.run(_run())
