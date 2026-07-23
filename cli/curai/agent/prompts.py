from __future__ import annotations

import subprocess
from pathlib import Path


def git_branch(workspace: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def build_system_prompt(workspace: Path) -> str:
    branch = git_branch(workspace)
    return f"""You are CurAI, a coding agent working in the user's project.

Workspace: {workspace}
Git branch: {branch}

Rules:
- Use tools to read, search, and modify code before guessing.
- Prefer small, focused edits (edit_file) over rewriting whole files.
- Run tests or linters with run_command when verifying changes.
- Stay inside the workspace. Do not access paths outside the project.
- When done, reply with a concise summary of what you changed and why.
"""
