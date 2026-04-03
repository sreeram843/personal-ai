"""Sandbox policy enforcement for tool execution."""

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from app.schemas.tool import ToolInvocationRequest, ToolInvocationResult, ToolSpec

logger = logging.getLogger(__name__)


class SandboxPolicyViolation(Exception):
    """Raised when a tool invocation violates sandbox policy."""

    pass


class SandboxPolicyEnforcer:
    """Enforces sandbox policies for tool execution."""

    def __init__(self) -> None:
        self._blocked_commands = {
            "rm",
            "rmdir",
            "dd",
            "mkfs",
            "fdisk",
            "shutdown",
            "reboot",
            "killall",
            "kill",
            "sudo",
            "su",
            "chmod",
            "chown",
        }
        self._dangerous_patterns = [
            r">\s*\/dev\/sda",  # Direct disk writes
            r">\s*\/proc",
            r">\s*\/sys",
            r"eval\s*\(",
            r"exec\s*\(",
        ]

    def validate_invocation(self, tool_spec: ToolSpec, request: ToolInvocationRequest) -> Tuple[bool, Optional[str]]:
        """Validate a tool invocation against the tool spec policy.

        Returns:
            (is_valid, error_message)
        """
        # Check role authorization
        if tool_spec.allowed_roles and request.role not in tool_spec.allowed_roles:
            return False, f"Role '{request.role}' is not allowed to use tool '{tool_spec.tool_id}'"

        # If tool defines allowed commands, validate shell inputs
        if tool_spec.allowed_commands is not None and isinstance(request.inputs.get("command"), str):
            command = request.inputs["command"].strip()
            if not self._is_command_allowed(command, tool_spec.allowed_commands):
                return False, f"Command '{command}' is not in the allowlist for this tool"

        # Check file access policies
        if "path" in request.inputs:
            path = request.inputs["path"]
            if not self._is_path_allowed(path, tool_spec.allowed_read_paths):
                return False, f"Read access denied for path: {path}"

        if "write_path" in request.inputs:
            path = request.inputs["write_path"]
            if tool_spec.allowed_write_paths is None:
                return False, "Tool does not have write permissions"
            if not self._is_path_allowed(path, tool_spec.allowed_write_paths):
                return False, f"Write access denied for path: {path}"

        return True, None

    def validate_command_execution(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate a shell command for dangerous patterns.

        Returns:
            (is_safe, error_message)
        """
        # Check blocked commands
        cmd_parts = command.split()
        if cmd_parts and cmd_parts[0] in self._blocked_commands:
            return False, f"Blocked command: {cmd_parts[0]}"

        # Check dangerous patterns
        for pattern in self._dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Command contains dangerous pattern: {pattern}"

        # Check for pipe into shell eval
        if re.search(r"\|\s*(sh|bash|python)", command):
            return False, "Piping into shell interpreters is not allowed"

        return True, None

    def _is_command_allowed(self, command: str, allowlist: list[str]) -> bool:
        """Check if command is in the allowlist."""
        cmd_parts = command.split()
        if not cmd_parts:
            return False
        base_cmd = cmd_parts[0]
        for allowed in allowlist:
            if base_cmd == allowed or command.startswith(allowed):
                return True
        return False

    def _is_path_allowed(self, path: str, allowlist: Optional[list[str]]) -> bool:
        """Check if path is in the allowlist.

        If allowlist is None (unrestricted), returns True for non-system paths.
        If allowlist is provided, only paths in the list are allowed.
        """
        try:
            # Use current working directory for relative path resolution
            if not path.startswith("/"):
                # Relative path - check if it's in an allowed workspace location
                if allowlist is None:
                    # No allowlist means all relative paths OK
                    return True
                # With allowlist, only allow specified relative paths
                for allowed in allowlist:
                    if allowed.startswith("/"):
                        continue  # Skip absolute paths when checking relative
                    if path.startswith(allowed):
                        return True
                return False
            
            abs_path = str(Path(path).resolve())
        except Exception:
            return False

        # Block system directories for absolute paths
        blocked_prefixes = {"/etc", "/sys", "/proc", "/dev", "/boot", "/root"}
        if any(abs_path.startswith(prefix) for prefix in blocked_prefixes):
            return False

        # If allowlist is none, deny absolute paths outside standard areas
        if allowlist is None:
            # Allow /tmp and /home for non-system absolute paths
            allowed_abs_roots = {"/tmp", "/home", "/var/tmp"}
            return any(abs_path.startswith(root) for root in allowed_abs_roots)

        # If allowlist specified, only allow those paths
        for allowed in allowlist:
            try:
                allowed_abs = str(Path(allowed).resolve())
                if abs_path.startswith(allowed_abs):
                    return True
            except Exception:
                continue

        return False

    async def execute_with_policy(
        self,
        tool_spec: ToolSpec,
        request: ToolInvocationRequest,
        executor_fn,
    ) -> ToolInvocationResult:
        """Execute a tool with sandbox policy enforcement."""
        # Validate invocation
        is_valid, error_msg = self.validate_invocation(tool_spec, request)
        if not is_valid:
            logger.warning(f"Policy violation for tool {tool_spec.tool_id}: {error_msg}")
            return ToolInvocationResult(tool_id=tool_spec.tool_id, success=False, output="", error=error_msg, duration_seconds=0.0)

        # Execute tool
        try:
            result = await executor_fn(request.inputs, timeout=tool_spec.timeout_seconds)
            output = str(result)

            # Truncate if needed
            was_truncated = False
            if len(output) > tool_spec.max_output_chars:
                output = output[: tool_spec.max_output_chars] + "\n[OUTPUT TRUNCATED]"
                was_truncated = True

            # Log invocation if audit enabled
            if tool_spec.audit_log:
                logger.info(f"Tool {tool_spec.tool_id} invoked by {request.role} with inputs: {request.inputs}")

            return ToolInvocationResult(
                tool_id=tool_spec.tool_id,
                success=True,
                output=output,
                duration_seconds=0.0,
                was_truncated=was_truncated,
            )
        except Exception as exc:
            logger.error(f"Tool execution failed: {exc}")
            return ToolInvocationResult(
                tool_id=tool_spec.tool_id,
                success=False,
                output="",
                error=str(exc),
                duration_seconds=0.0,
            )
