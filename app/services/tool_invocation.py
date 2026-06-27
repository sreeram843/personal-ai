"""Shared ToolRegistry invocation for chat agents."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.schemas.tool import ToolInvocationRequest, ToolSpec
from app.services.skill_context import get_skill_allowed_tools
from app.services.tool_permissions import evaluate_tool_permission, get_tool_execution_context
from app.services.tool_registry import ToolRegistry


def resolved_tool_query(*, query: str = "", user_query: str = "") -> str:
    return (query or user_query).strip()


async def invoke_agent_tool(
    registry: ToolRegistry,
    *,
    tool_id: str,
    spec: ToolSpec,
    role: str,
    arguments: Dict[str, Any],
    extra_inputs: Optional[Dict[str, Any]] = None,
) -> str:
    """Invoke a registry tool with permission checks and normalized query inputs."""
    text = resolved_tool_query(
        query=str(arguments.get("query") or ""),
        user_query=str(arguments.get("user_query") or ""),
    )
    inputs: Dict[str, Any] = dict(arguments)
    if text:
        inputs.setdefault("user_query", text)
        inputs.setdefault("query", text)
    if not text and not any(v not in (None, "") for v in arguments.values()):
        return "ERROR: tool requires a non-empty query or typed argument"
    if extra_inputs:
        inputs.update(extra_inputs)

    ctx = get_tool_execution_context()
    approved_by = None
    if ctx is not None:
        action, approved_by = evaluate_tool_permission(
            tool_id,
            spec,
            inputs=inputs,
            ctx=ctx,
        )
        if action == "plan_only":
            preview = ", ".join(f"{k}={v!r}" for k, v in list(inputs.items())[:4])
            return (
                f"PLANNED (not executed in plan mode): {spec.name}"
                + (f" — {preview}" if preview else "")
            )
        if action == "needs_approval":
            return (
                f"APPROVAL REQUIRED: {spec.name} ({tool_id}). "
                "Approve this tool in Agent Settings or resend with approved_tool_ids."
            )

    result = await registry.invoke_tool(
        ToolInvocationRequest(
            tool_id=tool_id,
            role=role,
            inputs=inputs,
            approved_by=approved_by,
        )
    )
    if result.success:
        return result.output
    return result.error or "Tool invocation failed"


def list_agent_tool_specs(registry: ToolRegistry, *, role: str) -> Dict[str, ToolSpec]:
    """Return tools visible to the agent, filtered by active skill context."""
    skill_allowed = get_skill_allowed_tools()
    merged = registry.list_tools_for_role(role)
    if skill_allowed is None:
        return merged
    return {tool_id: spec for tool_id, spec in merged.items() if tool_id in skill_allowed}


__all__ = [
    "invoke_agent_tool",
    "list_agent_tool_specs",
    "resolved_tool_query",
]
