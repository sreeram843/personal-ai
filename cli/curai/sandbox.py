from __future__ import annotations

import re
from pathlib import Path

BLOCKED_COMMANDS = {
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

DANGEROUS_PATTERNS = [
    r">\s*/dev/sda",
    r">\s*/proc",
    r">\s*/sys",
    r"eval\s*\(",
    r"exec\s*\(",
]

BLOCKED_PATH_PREFIXES = ("/etc", "/sys", "/proc", "/dev", "/boot", "/root")


class SandboxError(Exception):
    pass


def resolve_workspace_path(workspace: Path, user_path: str) -> Path:
    text = (user_path or "").strip()
    if not text:
        raise SandboxError("path is required")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = (workspace / candidate).resolve()
    else:
        candidate = candidate.resolve()
    workspace_resolved = workspace.resolve()
    try:
        candidate.relative_to(workspace_resolved)
    except ValueError as exc:
        raise SandboxError(f"path escapes workspace: {user_path}") from exc
    blocked = any(str(candidate).startswith(prefix) for prefix in BLOCKED_PATH_PREFIXES)
    if blocked:
        raise SandboxError(f"access denied: {user_path}")
    return candidate


def validate_command(command: str) -> None:
    text = (command or "").strip()
    if not text:
        raise SandboxError("command is required")
    parts = text.split()
    if parts and parts[0] in BLOCKED_COMMANDS:
        raise SandboxError(f"blocked command: {parts[0]}")
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise SandboxError(f"command contains dangerous pattern: {pattern}")
    if re.search(r"\|\s*(sh|bash|python)", text):
        raise SandboxError("piping into shell interpreters is not allowed")
