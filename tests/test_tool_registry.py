"""Tests for tool registry and sandbox policy enforcement."""

import asyncio

import pytest

from app.schemas.tool import ToolCapability, ToolInvocationRequest, ToolRiskClass, ToolSpec
from app.services.sandbox_policy import SandboxPolicyEnforcer
from app.services.tool_registry import ToolRegistry


def test_sandbox_policy_blocks_forbidden_commands() -> None:
    enforcer = SandboxPolicyEnforcer()

    # Test blocked commands
    dangerous_commands = [
        "rm -rf /",
        "sudo shutdown -h now",
        "kill -9 1",
        "chmod 777 /etc/passwd",
    ]

    for cmd in dangerous_commands:
        is_safe, error = enforcer.validate_command_execution(cmd)
        assert not is_safe, f"Command should be blocked: {cmd}"
        assert error is not None


def test_sandbox_policy_allows_safe_commands() -> None:
    enforcer = SandboxPolicyEnforcer()

    safe_commands = [
        "ls -la /home/user",
        "echo hello world",
        "grep pattern file.txt",
        "wc -l document.txt",
    ]

    for cmd in safe_commands:
        is_safe, error = enforcer.validate_command_execution(cmd)
        assert is_safe, f"Safe command blocked: {cmd}, error: {error}"


def test_sandbox_policy_blocks_shell_pipes() -> None:
    enforcer = SandboxPolicyEnforcer()

    dangerous = [
        "cat file.txt | sh",
        "curl http://example.com | bash",
        "python -m something | python",
    ]

    for cmd in dangerous:
        is_safe, error = enforcer.validate_command_execution(cmd)
        assert not is_safe, f"Pipe to shell should be blocked: {cmd}"


def test_sandbox_policy_validates_file_paths() -> None:
    enforcer = SandboxPolicyEnforcer()

    # System paths should be blocked
    assert not enforcer._is_path_allowed("/etc/passwd", None)
    assert not enforcer._is_path_allowed("/proc/1/mem", None)
    assert not enforcer._is_path_allowed("/sys/kernel/debug", None)

    # Workspace paths should be allowed when no allowlist
    assert enforcer._is_path_allowed("./src/main.py", None)
    assert enforcer._is_path_allowed("docs/README.md", None)


def test_sandbox_policy_enforces_read_allowlist() -> None:
    enforcer = SandboxPolicyEnforcer()

    # With allowlist, only those paths allowed
    allowlist = ["/tmp/safe", "/home/user/data"]
    assert enforcer._is_path_allowed("/tmp/safe/file.txt", allowlist)
    assert enforcer._is_path_allowed("/home/user/data/doc.pdf", allowlist)
    assert not enforcer._is_path_allowed("/var/log/app.log", allowlist)


def test_tool_registry_registers_and_retrieves_tools() -> None:
    registry = ToolRegistry()

    tool_spec = ToolSpec(
        tool_id="read_file",
        name="Read File",
        description="Read file contents",
        risk_class=ToolRiskClass.FILESYSTEM,
        capabilities={ToolCapability.READ_FILES},
        allowed_roles={"researcher", "synthesizer"},
        allowed_read_paths=["./docs", "./src"],
    )

    async def read_executor(inputs, timeout):
        return "file contents"

    registry.register_tool(tool_spec, read_executor)

    # Retrieve tool
    retrieved = registry.get_tool("read_file")
    assert retrieved is not None
    assert retrieved.tool_id == "read_file"
    assert retrieved.risk_class == ToolRiskClass.FILESYSTEM


def test_tool_registry_enforces_role_based_access() -> None:
    registry = ToolRegistry()

    tool_spec = ToolSpec(
        tool_id="admin_tool",
        name="Admin Tool",
        description="Admin-only tool",
        risk_class=ToolRiskClass.DANGEROUS,
        allowed_roles={"coordinator"},  # Only coordinator
    )

    async def dummy_executor(inputs, timeout):
        return "result"

    registry.register_tool(tool_spec, dummy_executor)

    # Test role authorization
    allowed_tools = registry.list_tools_for_role("coordinator")
    assert "admin_tool" in allowed_tools

    allowed_tools = registry.list_tools_for_role("researcher")
    assert "admin_tool" not in allowed_tools


def test_tool_registry_filters_by_capability() -> None:
    registry = ToolRegistry()

    # Register tools with different capabilities
    spec1 = ToolSpec(
        tool_id="git_clone",
        name="Git Clone",
        description="Clone repository",
        risk_class=ToolRiskClass.NETWORK,
        capabilities={ToolCapability.GIT_CLONE, ToolCapability.NETWORK_REQUEST},
    )

    spec2 = ToolSpec(
        tool_id="read_file",
        name="Read File",
        description="Read file",
        risk_class=ToolRiskClass.FILESYSTEM,
        capabilities={ToolCapability.READ_FILES},
    )

    async def dummy(inputs, timeout):
        return ""

    registry.register_tool(spec1, dummy)
    registry.register_tool(spec2, dummy)

    # Filter by capability
    git_tools = registry.list_tools_by_capability(ToolCapability.GIT_CLONE)
    assert len(git_tools) == 1
    assert "git_clone" in git_tools

    read_tools = registry.list_tools_by_capability(ToolCapability.READ_FILES)
    assert len(read_tools) == 1
    assert "read_file" in read_tools


def test_tool_invocation_validates_command_whitelist() -> None:
    enforcer = SandboxPolicyEnforcer()

    tool_spec = ToolSpec(
        tool_id="safe_shell",
        name="Safe Shell",
        description="Execute whitelisted commands",
        risk_class=ToolRiskClass.SHELL,
        allowed_commands=["ls", "echo", "grep"],
    )

    # Valid command
    request = ToolInvocationRequest(tool_id="safe_shell", role="researcher", inputs={"command": "ls -la"})
    is_valid, error = enforcer.validate_invocation(tool_spec, request)
    assert is_valid

    # Invalid command (not whitelisted)
    request = ToolInvocationRequest(tool_id="safe_shell", role="researcher", inputs={"command": "rm -rf /"})
    is_valid, error = enforcer.validate_invocation(tool_spec, request)
    assert not is_valid


def test_tool_invocation_rejects_unauthorized_role() -> None:
    enforcer = SandboxPolicyEnforcer()

    tool_spec = ToolSpec(
        tool_id="restricted",
        name="Restricted Tool",
        description="Role-restricted",
        risk_class=ToolRiskClass.DANGEROUS,
        allowed_roles={"coordinator"},
    )

    # Researcher tries to use coordinator-only tool
    request = ToolInvocationRequest(tool_id="restricted", role="researcher", inputs={})
    is_valid, error = enforcer.validate_invocation(tool_spec, request)
    assert not is_valid
    assert "not allowed" in error.lower()


def test_tool_invocation_enforces_file_read_policy() -> None:
    enforcer = SandboxPolicyEnforcer()

    tool_spec = ToolSpec(
        tool_id="read_docs",
        name="Read Docs",
        description="Read documentation",
        risk_class=ToolRiskClass.FILESYSTEM,
        allowed_read_paths=["./docs", "./README.md"],
    )

    # Allowed path
    request = ToolInvocationRequest(tool_id="read_docs", role="researcher", inputs={"path": "./docs/guide.md"})
    is_valid, error = enforcer.validate_invocation(tool_spec, request)
    assert is_valid

    # Blocked path
    request = ToolInvocationRequest(tool_id="read_docs", role="researcher", inputs={"path": "/etc/passwd"})
    is_valid, error = enforcer.validate_invocation(tool_spec, request)
    assert not is_valid


def test_tool_invocation_blocks_write_when_disabled() -> None:
    enforcer = SandboxPolicyEnforcer()

    # Tool with write disabled (allowed_write_paths = None)
    tool_spec = ToolSpec(
        tool_id="read_only",
        name="Read Only",
        description="Read-only tool",
        risk_class=ToolRiskClass.FILESYSTEM,
        allowed_write_paths=None,
    )

    request = ToolInvocationRequest(tool_id="read_only", role="researcher", inputs={"write_path": "./output.txt"})
    is_valid, error = enforcer.validate_invocation(tool_spec, request)
    assert not is_valid
    assert "does not have write" in error.lower()


@pytest.mark.asyncio
async def test_tool_registry_invocation_full_flow() -> None:
    registry = ToolRegistry()

    tool_spec = ToolSpec(
        tool_id="echo_tool",
        name="Echo",
        description="Echo input",
        risk_class=ToolRiskClass.SAFE,
        allowed_roles={"researcher", "synthesizer"},
        timeout_seconds=5,
    )

    async def echo_executor(inputs, timeout):
        return inputs.get("message", "")

    registry.register_tool(tool_spec, echo_executor)

    # Valid invocation
    request = ToolInvocationRequest(tool_id="echo_tool", role="researcher", inputs={"message": "hello"})
    result = await registry.invoke_tool(request)

    assert result.success
    assert result.output == "hello"
    assert result.error is None


def test_tool_registry_invocation_full_flow_sync() -> None:
    """Synchronous wrapper for async test."""
    asyncio.run(test_tool_registry_invocation_full_flow())


@pytest.mark.asyncio
async def test_tool_registry_rejects_unauthorized_invocation() -> None:
    registry = ToolRegistry()

    tool_spec = ToolSpec(
        tool_id="admin_only",
        name="Admin",
        description="Admin tool",
        risk_class=ToolRiskClass.DANGEROUS,
        allowed_roles={"coordinator"},
    )

    async def dummy(inputs, timeout):
        return "admin result"

    registry.register_tool(tool_spec, dummy)

    # Researcher tries admin tool
    request = ToolInvocationRequest(tool_id="admin_only", role="researcher", inputs={})
    result = await registry.invoke_tool(request)

    assert not result.success
    assert "not authorized" in result.error.lower()


def test_tool_registry_rejects_unauthorized_invocation_sync() -> None:
    """Synchronous wrapper for async test."""
    asyncio.run(test_tool_registry_rejects_unauthorized_invocation())


def test_tool_registry_summary() -> None:
    registry = ToolRegistry()

    tool_spec = ToolSpec(
        tool_id="example",
        name="Example",
        description="Example tool",
        risk_class=ToolRiskClass.FILESYSTEM,
        capabilities={ToolCapability.READ_FILES},
    )

    async def dummy(inputs, timeout):
        return ""

    registry.register_tool(tool_spec, dummy)

    summary = registry.get_registry_summary()
    assert "filesystem" in summary
    assert len(summary["filesystem"]) == 1
    assert summary["filesystem"][0]["tool_id"] == "example"


@pytest.mark.asyncio
async def test_high_risk_tool_requires_capability_token() -> None:
    registry = ToolRegistry()
    tool_spec = ToolSpec(
        tool_id="shell_tool",
        name="Shell Tool",
        description="Executes shell commands",
        risk_class=ToolRiskClass.SHELL,
        allowed_roles={"researcher"},
    )

    async def dummy(inputs, timeout):
        return "ok"

    registry.register_tool(tool_spec, dummy)

    denied = await registry.invoke_tool(
        ToolInvocationRequest(tool_id="shell_tool", role="researcher", inputs={"command": "echo hi"})
    )
    assert not denied.success
    assert "capability token" in (denied.error or "").lower()

    grant = registry.issue_capability_grant(tool_id="shell_tool", role="researcher")
    allowed = await registry.invoke_tool(
        ToolInvocationRequest(
            tool_id="shell_tool",
            role="researcher",
            inputs={"command": "echo hi"},
            capability_token=grant.token,
        )
    )
    assert allowed.success


def test_high_risk_tool_requires_capability_token_sync() -> None:
    asyncio.run(test_high_risk_tool_requires_capability_token())


@pytest.mark.asyncio
async def test_tool_approval_policy_enforced() -> None:
    registry = ToolRegistry()
    tool_spec = ToolSpec(
        tool_id="prod_deploy",
        name="Prod Deploy",
        description="Deploys production artifacts",
        risk_class=ToolRiskClass.SHELL,
        allowed_roles={"coordinator"},
        requires_approval=True,
        approval_policy={"required_approver_role": "security"},
    )

    async def dummy(inputs, timeout):
        return "deployed"

    registry.register_tool(tool_spec, dummy)
    grant = registry.issue_capability_grant(tool_id="prod_deploy", role="coordinator")

    denied = await registry.invoke_tool(
        ToolInvocationRequest(
            tool_id="prod_deploy",
            role="coordinator",
            inputs={"command": "echo deploy"},
            capability_token=grant.token,
            approved_by="ops:alice",
        )
    )
    assert not denied.success
    assert "approver" in (denied.error or "").lower()

    approved = await registry.invoke_tool(
        ToolInvocationRequest(
            tool_id="prod_deploy",
            role="coordinator",
            inputs={"command": "echo deploy"},
            capability_token=grant.token,
            approved_by="security:bob",
        )
    )
    assert approved.success
    assert approved.approved_by == "security:bob"


def test_tool_approval_policy_enforced_sync() -> None:
    asyncio.run(test_tool_approval_policy_enforced())
