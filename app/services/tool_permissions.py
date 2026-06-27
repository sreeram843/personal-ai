"""Tool permission modes inspired by agent CLIs — auto, ask, plan."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Set

from app.schemas.agent import ChatAgentOptions, PendingToolApproval, PlannedToolCall, ToolPermissionMode
from app.schemas.tool import ToolRiskClass, ToolSpec

ToolPermissionAction = Literal["execute", "plan_only", "needs_approval"]


@dataclass
class ToolExecutionContext:
    permission_mode: ToolPermissionMode = "auto"
    approved_tool_ids: Set[str] = field(default_factory=set)
    user_id: str = ""
    planned: List[PlannedToolCall] = field(default_factory=list)
    pending_approvals: List[PendingToolApproval] = field(default_factory=list)


_execution_context: ContextVar[Optional[ToolExecutionContext]] = ContextVar("tool_execution_context", default=None)


def activate_tool_execution_context(options: ChatAgentOptions, *, user_id: str) -> Token:
    ctx = ToolExecutionContext(
        permission_mode=options.tool_permission_mode,
        approved_tool_ids=set(options.approved_tool_ids),
        user_id=user_id,
    )
    return _execution_context.set(ctx)


def deactivate_tool_execution_context(token: Token) -> None:
    _execution_context.reset(token)


def get_tool_execution_context() -> Optional[ToolExecutionContext]:
    return _execution_context.get()


def _inputs_preview(inputs: dict) -> dict:
    preview = {}
    for key, value in (inputs or {}).items():
        if key in {"user_id"}:
            continue
        text = str(value)
        preview[key] = text if len(text) <= 120 else f"{text[:117]}…"
    return preview


def _is_read_only_tool(tool_id: str, spec: ToolSpec) -> bool:
    name = f"{tool_id} {spec.name}".lower()
    read_hints = ("get_", "list_", "search_", "read_", "fetch_", "lookup_", "find_")
    if any(hint in name for hint in read_hints):
        return True
    if spec.risk_class == ToolRiskClass.SAFE:
        return True
    return False


def tool_requires_user_approval(tool_id: str, spec: ToolSpec) -> bool:
    if spec.requires_approval:
        return True
    if tool_id.startswith("mcp_") and not _is_read_only_tool(tool_id, spec):
        return True
    if spec.risk_class in {ToolRiskClass.SHELL, ToolRiskClass.DANGEROUS, ToolRiskClass.FILESYSTEM}:
        return True
    return False


def evaluate_tool_permission(
    tool_id: str,
    spec: ToolSpec,
    *,
    inputs: dict,
    ctx: ToolExecutionContext,
) -> tuple[ToolPermissionAction, Optional[str]]:
    preview = _inputs_preview(inputs)

    if ctx.permission_mode == "plan":
        ctx.planned.append(
            PlannedToolCall(
                tool_id=tool_id,
                name=spec.name,
                reason="Plan mode — tool not executed",
                inputs_preview=preview,
            )
        )
        return "plan_only", None

    if ctx.permission_mode == "ask" and tool_requires_user_approval(tool_id, spec):
        if tool_id not in ctx.approved_tool_ids:
            ctx.pending_approvals.append(
                PendingToolApproval(
                    tool_id=tool_id,
                    name=spec.name,
                    description=spec.description,
                    risk_class=str(spec.risk_class.value if hasattr(spec.risk_class, "value") else spec.risk_class),
                    inputs_preview=preview,
                )
            )
            return "needs_approval", None

    approved_by: Optional[str] = None
    if spec.requires_approval or tool_requires_user_approval(tool_id, spec):
        if ctx.permission_mode == "auto":
            approved_by = f"auto:{ctx.user_id or 'system'}"
        elif tool_id in ctx.approved_tool_ids:
            approved_by = f"user:{ctx.user_id or 'system'}"
    return "execute", approved_by


__all__ = [
    "ToolExecutionContext",
    "activate_tool_execution_context",
    "deactivate_tool_execution_context",
    "evaluate_tool_permission",
    "get_tool_execution_context",
    "tool_requires_user_approval",
]
