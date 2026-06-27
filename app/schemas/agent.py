"""Agent runtime settings: tool permissions, MCP, planned/pending tool calls."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ToolPermissionMode = Literal["auto", "ask", "plan"]


class PlannedToolCall(BaseModel):
    tool_id: str
    name: str
    reason: str
    inputs_preview: Dict[str, Any] = Field(default_factory=dict)


class PendingToolApproval(BaseModel):
    tool_id: str
    name: str
    description: str
    risk_class: str
    inputs_preview: Dict[str, Any] = Field(default_factory=dict)


class ChatAgentOptions(BaseModel):
    """Per-request agent controls (from ChatRequest.options)."""

    tool_permission_mode: ToolPermissionMode = "auto"
    approved_tool_ids: List[str] = Field(default_factory=list)

    @classmethod
    def from_request_options(cls, options: Optional[Dict[str, Any]]) -> "ChatAgentOptions":
        raw = options or {}
        mode = str(raw.get("tool_permission_mode") or "auto").strip().lower()
        if mode not in {"auto", "ask", "plan"}:
            mode = "auto"
        approved = raw.get("approved_tool_ids") or []
        if not isinstance(approved, list):
            approved = []
        return cls(
            tool_permission_mode=mode,  # type: ignore[arg-type]
            approved_tool_ids=[str(item) for item in approved if str(item).strip()],
        )


class McpServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    url: str = Field(..., min_length=8)
    enabled: bool = True
    headers: Dict[str, str] = Field(default_factory=dict)


class McpServerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    url: Optional[str] = Field(default=None, min_length=8)
    enabled: Optional[bool] = None
    headers: Optional[Dict[str, str]] = None


class McpServerResponse(BaseModel):
    id: str
    name: str
    url: str
    enabled: bool
    header_keys: List[str] = Field(default_factory=list)
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    tool_count: int = 0
    last_checked_at: Optional[str] = None


class McpServerListResponse(BaseModel):
    servers: List[McpServerResponse]


class McpServerTestResponse(BaseModel):
    ok: bool
    tool_count: int = 0
    tools: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class DoctorReportResponse(BaseModel):
    status: str
    issues: List[str] = Field(default_factory=list)
    features: Dict[str, Any] = Field(default_factory=dict)
    checks: Dict[str, Any] = Field(default_factory=dict)


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    triggers: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    enabled: bool = True
    bundled: bool = False
    pick_only: bool = False


class AssistantResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    instructions: str = ""
    triggers: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    enabled: bool = True
    bundled: bool = False
    pick_only: bool = False
    is_default: bool = False


class AssistantListResponse(BaseModel):
    assistants: List[AssistantResponse]


class AssistantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = ""
    instructions: str = Field(default="", max_length=4000)
    allowed_tools: List[str] = Field(default_factory=list)
    triggers: List[str] = Field(default_factory=list)
    pick_only: bool = True


class AssistantUpdate(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = None
    instructions: Optional[str] = Field(default=None, max_length=4000)
    allowed_tools: Optional[List[str]] = None
    triggers: Optional[List[str]] = None
    pick_only: Optional[bool] = None


class SkillListResponse(BaseModel):
    skills: List[SkillResponse]


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = ""
    triggers: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    system_addendum: str = Field(default="", max_length=4000)


class SkillUpdate(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = None
    triggers: Optional[List[str]] = None
    allowed_tools: Optional[List[str]] = None
    system_addendum: Optional[str] = Field(default=None, max_length=4000)


class AgentTaskResponse(BaseModel):
    id: str
    title: str
    detail: str = ""
    status: Literal["pending", "in_progress", "completed", "cancelled"]
    source: Literal["planned_tool", "user", "skill"] = "user"
    tool_id: Optional[str] = None
    conversation_id: Optional[str] = None
    created_at: str
    updated_at: str


class AgentTaskListResponse(BaseModel):
    tasks: List[AgentTaskResponse]


class AgentTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    detail: str = Field(default="", max_length=2000)
    conversation_id: Optional[str] = None


class AgentTaskStatusUpdate(BaseModel):
    status: Literal["pending", "in_progress", "completed", "cancelled"]


__all__ = [
    "AgentTaskCreate",
    "AgentTaskListResponse",
    "AgentTaskResponse",
    "AgentTaskStatusUpdate",
    "AssistantCreate",
    "AssistantListResponse",
    "AssistantResponse",
    "AssistantUpdate",
    "ChatAgentOptions",
    "DoctorReportResponse",
    "McpServerCreate",
    "McpServerListResponse",
    "McpServerResponse",
    "McpServerTestResponse",
    "McpServerUpdate",
    "PendingToolApproval",
    "PlannedToolCall",
    "SkillCreate",
    "SkillListResponse",
    "SkillResponse",
    "SkillUpdate",
    "ToolPermissionMode",
]
