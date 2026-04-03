"""Tool specification and capability schemas."""

from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class ToolRiskClass(str, Enum):
    """Risk classification for tool capabilities."""

    SAFE = "safe"  # No external side effects, read-only operations
    NETWORK = "network"  # Requires outbound network access
    FILESYSTEM = "filesystem"  # Reads/writes to filesystem
    SHELL = "shell"  # Executes shell commands
    DANGEROUS = "dangerous"  # Multi-risk or destructive (execute arbitrary code, delete files)


class ToolCapability(str, Enum):
    """Fine-grained tool capabilities."""

    READ_CODE = "read_code"
    WRITE_CODE = "write_code"
    EXECUTE_SHELL = "execute_shell"
    READ_FILES = "read_files"
    WRITE_FILES = "write_files"
    DELETE_FILES = "delete_files"
    NETWORK_REQUEST = "network_request"
    GIT_CLONE = "git_clone"
    GIT_PUSH = "git_push"
    DATABASE_QUERY = "database_query"
    DATABASE_WRITE = "database_write"


class ToolSpec(BaseModel):
    """Tool specification with capability tags and execution policy."""

    tool_id: str = Field(..., description="Unique identifier for the tool")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool functionality description")
    version: str = Field(default="1.0.0", description="Tool version")
    risk_class: ToolRiskClass = Field(..., description="Risk classification")
    capabilities: Set[ToolCapability] = Field(default_factory=set, description="Set of capabilities this tool provides")
    allowed_roles: Set[str] = Field(default_factory=lambda: {"coordinator", "researcher", "synthesizer"}, description="Roles that can invoke this tool")
    timeout_seconds: int = Field(default=30, description="Max execution time in seconds")
    max_output_chars: int = Field(default=10000, description="Max output size in characters before truncation")
    allowed_read_paths: Optional[List[str]] = Field(default=None, description="Allowlist of paths for read operations (None = no restriction)")
    allowed_write_paths: Optional[List[str]] = Field(default=None, description="Allowlist of paths for write operations (None = disabled)")
    allowed_commands: Optional[List[str]] = Field(default=None, description="Allowlist of shell commands (None = no shell access)")
    allowed_domains: Optional[List[str]] = Field(default=None, description="Allowlist of domains for network requests")
    requires_approval: bool = Field(default=False, description="Requires human approval before execution")
    approval_policy: Dict[str, str] = Field(default_factory=dict, description="Approval-as-code policy metadata")
    audit_log: bool = Field(default=True, description="Whether to audit-log invocations")

    class Config:
        use_enum_values = False


class ToolInvocationRequest(BaseModel):
    """Request to invoke a tool."""

    tool_id: str
    role: str
    inputs: dict = Field(default_factory=dict, description="Tool inputs")
    capability_token: Optional[str] = Field(default=None, description="Scoped capability token for high-risk tools")
    approved_by: Optional[str] = Field(default=None, description="Approver identity if approval is required")


class ToolInvocationResult(BaseModel):
    """Result of a tool invocation."""

    tool_id: str
    success: bool
    output: str
    error: Optional[str] = None
    duration_seconds: float
    was_truncated: bool = False
    approved_by: Optional[str] = None


class CapabilityGrant(BaseModel):
    """Scoped, expiring permission to invoke a tool."""

    token: str
    tool_id: str
    role: str
    issued_at: datetime
    expires_at: datetime
    metadata: Dict[str, str] = Field(default_factory=dict)
