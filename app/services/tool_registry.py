"""Centralized tool registry with role-based access control."""

from datetime import datetime, timedelta
import logging
from typing import Dict, Optional
from uuid import uuid4

from app.schemas.tool import (
    CapabilityGrant,
    ToolCapability,
    ToolInvocationRequest,
    ToolInvocationResult,
    ToolRiskClass,
    ToolSpec,
)
from app.services.sandbox_policy import SandboxPolicyEnforcer, SandboxPolicyViolation

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for available tools with RBAC and sandbox policy enforcement."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}
        self._executor_map: Dict[str, callable] = {}
        self._capability_grants: Dict[str, CapabilityGrant] = {}
        self._enforcer = SandboxPolicyEnforcer()

    def register_tool(self, tool_spec: ToolSpec, executor_fn: callable) -> None:
        """Register a tool with execution function.

        Args:
            tool_spec: Tool specification with policies
            executor_fn: Async callable that executes the tool
        """
        if tool_spec.tool_id in self._tools:
            logger.warning(f"Tool {tool_spec.tool_id} already registered, overwriting")

        self._tools[tool_spec.tool_id] = tool_spec
        self._executor_map[tool_spec.tool_id] = executor_fn
        logger.info(f"Registered tool: {tool_spec.tool_id} (risk: {tool_spec.risk_class})")

    def get_tool(self, tool_id: str) -> Optional[ToolSpec]:
        """Get tool specification by ID."""
        return self._tools.get(tool_id)

    def list_tools_for_role(self, role: str) -> Dict[str, ToolSpec]:
        """List all tools available to a specific role."""
        return {tool_id: spec for tool_id, spec in self._tools.items() if role in spec.allowed_roles}

    def list_tools_by_capability(self, capability: ToolCapability) -> Dict[str, ToolSpec]:
        """List all tools that provide a specific capability."""
        return {tool_id: spec for tool_id, spec in self._tools.items() if capability in spec.capabilities}

    async def invoke_tool(self, request: ToolInvocationRequest) -> ToolInvocationResult:
        """Invoke a tool with policy enforcement.

        Returns:
            ToolInvocationResult with success status and output/error
        """
        tool_spec = self.get_tool(request.tool_id)
        if not tool_spec:
            return ToolInvocationResult(
                tool_id=request.tool_id,
                success=False,
                output="",
                error=f"Tool not found: {request.tool_id}",
                duration_seconds=0.0,
            )

        # Check role authorization
        if tool_spec.allowed_roles and request.role not in tool_spec.allowed_roles:
            error = f"Role '{request.role}' is not authorized to use tool '{request.tool_id}'"
            logger.warning(error)
            return ToolInvocationResult(
                tool_id=request.tool_id,
                success=False,
                output="",
                error=error,
                duration_seconds=0.0,
            )

        # Require explicit scoped capability grants for high-risk tools.
        if tool_spec.risk_class in {ToolRiskClass.SHELL, ToolRiskClass.DANGEROUS}:
            if not self._validate_capability_token(request.capability_token, request.role, request.tool_id):
                return ToolInvocationResult(
                    tool_id=request.tool_id,
                    success=False,
                    output="",
                    error="Missing or invalid capability token for high-risk tool",
                    duration_seconds=0.0,
                )

        if tool_spec.requires_approval:
            approved_by = (request.approved_by or "").strip()
            if not approved_by:
                return ToolInvocationResult(
                    tool_id=request.tool_id,
                    success=False,
                    output="",
                    error="Approval required but no approver was provided",
                    duration_seconds=0.0,
                )
            required_role = tool_spec.approval_policy.get("required_approver_role", "")
            if required_role and not approved_by.startswith(f"{required_role}:"):
                return ToolInvocationResult(
                    tool_id=request.tool_id,
                    success=False,
                    output="",
                    error=f"Approver must satisfy policy role '{required_role}'",
                    duration_seconds=0.0,
                )

        # Validate against sandbox policy
        is_valid, error_msg = self._enforcer.validate_invocation(tool_spec, request)
        if not is_valid:
            logger.warning(f"Sandbox policy violation: {error_msg}")
            return ToolInvocationResult(
                tool_id=request.tool_id,
                success=False,
                output="",
                error=error_msg,
                duration_seconds=0.0,
            )

        # Execute with enforcer
        executor = self._executor_map.get(request.tool_id)
        if not executor:
            return ToolInvocationResult(
                tool_id=request.tool_id,
                success=False,
                output="",
                error="No executor registered for tool",
                duration_seconds=0.0,
            )

        result = await self._enforcer.execute_with_policy(tool_spec, request, executor)
        result.approved_by = request.approved_by
        return result

    def issue_capability_grant(
        self,
        *,
        tool_id: str,
        role: str,
        ttl_seconds: int = 300,
        metadata: Optional[Dict[str, str]] = None,
    ) -> CapabilityGrant:
        """Issue a short-lived capability token for high-risk tool invocation."""
        now = datetime.utcnow()
        grant = CapabilityGrant(
            token=uuid4().hex,
            tool_id=tool_id,
            role=role,
            issued_at=now,
            expires_at=now + timedelta(seconds=max(10, ttl_seconds)),
            metadata=metadata or {},
        )
        self._capability_grants[grant.token] = grant
        return grant

    def _validate_capability_token(self, token: Optional[str], role: str, tool_id: str) -> bool:
        if not token:
            return False
        grant = self._capability_grants.get(token)
        if not grant:
            return False
        if grant.tool_id != tool_id or grant.role != role:
            return False
        if datetime.utcnow() > grant.expires_at:
            self._capability_grants.pop(token, None)
            return False
        return True

    def get_registry_summary(self) -> dict:
        """Return summary of registered tools grouped by risk class."""
        summary = {risk_class: [] for risk_class in ToolRiskClass}
        for tool_spec in self._tools.values():
            summary[tool_spec.risk_class.value].append(
                {
                    "tool_id": tool_spec.tool_id,
                    "name": tool_spec.name,
                    "capabilities": list(tool_spec.capabilities),
                    "allowed_roles": list(tool_spec.allowed_roles),
                    "timeout_seconds": tool_spec.timeout_seconds,
                }
            )
        return summary
