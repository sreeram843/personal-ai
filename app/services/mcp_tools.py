"""Register per-user MCP tools into the active ToolRegistry session overlay."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, Tuple

from app.core.config import Settings
from app.schemas.tool import ToolCapability, ToolRiskClass, ToolSpec
from app.services.builtin_tools import CHAT_AGENT_ROLE
from app.services.mcp_client import McpHttpClient, McpToolDefinition
from app.services.mcp_store import McpServerRecord, McpServerStore
from app.services.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

_MCP_TOOL_ID_PREFIX = "mcp_"


def mcp_tool_id(server_id: str, tool_name: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", tool_name).strip("_").lower()
    return f"{_MCP_TOOL_ID_PREFIX}{server_id}_{safe_name}"


def _risk_for_mcp_tool(tool_name: str, description: str) -> tuple[ToolRiskClass, bool]:
    label = f"{tool_name} {description}".lower()
    read_hints = ("get_", "list_", "search_", "read_", "fetch_", "lookup_", "find_", "query_")
    if any(hint in label for hint in read_hints):
        return ToolRiskClass.NETWORK, False
    write_hints = ("create_", "update_", "delete_", "write_", "post_", "push_", "merge_", "deploy_")
    if any(hint in label for hint in write_hints):
        return ToolRiskClass.NETWORK, True
    return ToolRiskClass.NETWORK, True


def _build_executor(client: McpHttpClient, tool_name: str) -> Callable:
    async def _executor(inputs: dict, timeout: float) -> str:
        arguments = dict(inputs or {})
        arguments.pop("user_id", None)
        if "query" in arguments and len(arguments) == 1:
            arguments = {"query": arguments["query"]}
        return await client.call_tool(tool_name, arguments)

    return _executor


def _tool_spec_for_mcp(server: McpServerRecord, tool: McpToolDefinition) -> ToolSpec:
    tool_id = mcp_tool_id(server.id, tool.name)
    risk_class, requires_approval = _risk_for_mcp_tool(tool.name, tool.description)
    return ToolSpec(
        tool_id=tool_id,
        name=f"{server.name}: {tool.name}",
        description=f"[MCP:{server.name}] {tool.description}",
        risk_class=risk_class,
        capabilities={ToolCapability.NETWORK_REQUEST},
        allowed_roles={CHAT_AGENT_ROLE},
        timeout_seconds=45,
        max_output_chars=12000,
        requires_approval=requires_approval,
        approval_policy={"source": "mcp", "server_id": server.id},
    )


async def discover_user_mcp_tools(
    *,
    store: McpServerStore,
    user_id: str,
    settings: Settings,
) -> Tuple[Dict[str, tuple[ToolSpec, Callable]], Dict[str, str]]:
    """Discover MCP tools for a user (does not mutate ToolRegistry)."""
    if not settings.enable_runtime_mcp or not user_id:
        return {}, {}

    session_tools: Dict[str, tuple[ToolSpec, Callable]] = {}
    errors: Dict[str, str] = {}

    for server in store.list_for_user(user_id):
        if not server.enabled or not server.url:
            continue
        client = McpHttpClient(
            url=server.url,
            headers=server.headers or {},
            timeout=settings.mcp_connect_timeout,
        )
        try:
            tools = await client.list_tools()
            for tool in tools:
                spec = _tool_spec_for_mcp(server, tool)
                session_tools[spec.tool_id] = (spec, _build_executor(client, tool.name))
            store.record_status(server.id, user_id=user_id, status="connected", tool_count=len(tools))
        except Exception as exc:
            message = str(exc)
            errors[server.id] = message
            store.record_status(server.id, user_id=user_id, status="error", tool_count=0, error=message)
            logger.warning("MCP server %s failed for user %s: %s", server.id, user_id, message)

    if session_tools:
        logger.info("Discovered %s MCP tools for user %s", len(session_tools), user_id)
    return session_tools, errors


async def load_user_mcp_session_tools(
    *,
    registry: ToolRegistry,
    store: McpServerStore,
    user_id: str,
    settings: Settings,
) -> Tuple[object, Dict[str, str]]:
    session_tools, errors = await discover_user_mcp_tools(store=store, user_id=user_id, settings=settings)
    token = registry.activate_session_tools(session_tools)
    return token, errors


def summarize_mcp_inputs(inputs: dict) -> str:
    cleaned = {k: v for k, v in (inputs or {}).items() if k != "user_id"}
    try:
        return json.dumps(cleaned, ensure_ascii=False)[:500]
    except TypeError:
        return str(cleaned)[:500]


__all__ = [
    "discover_user_mcp_tools",
    "load_user_mcp_session_tools",
    "mcp_tool_id",
    "summarize_mcp_inputs",
]
