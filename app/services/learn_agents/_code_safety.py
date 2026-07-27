"""Static safety check for LLM-generated Python before it's ever executed.

This is a denylist, not a sandbox: it walks the AST for the modules/names
that would let generated code touch the filesystem, network, or process
table, and refuses to run anything that imports or references them. It does
not replace OS-level isolation — for this personal lab, subprocess isolation
plus a short timeout plus this denylist is the deliberate tradeoff. Shared by
the Phase 4 coding agent and the Phase 7 tool-builder.
"""

from __future__ import annotations

import ast
from typing import Optional

_BANNED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "requests",
    "httpx",
    "urllib",
    "ctypes",
    "ftplib",
    "smtplib",
    "multiprocessing",
    "threading",
    "importlib",
    "pickle",
    "marshal",
    "signal",
}

_BANNED_NAMES = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
}


def check_code_safety(code: str) -> Optional[str]:
    """Return an error message if `code` is unsafe to execute, else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BANNED_MODULES:
                    return f"import of banned module '{root}'"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _BANNED_MODULES:
                return f"import of banned module '{root}'"
        elif isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            return f"use of banned name '{node.id}'"
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_NAMES:
            return f"use of banned attribute '{node.attr}'"

    return None


__all__ = ["check_code_safety"]
