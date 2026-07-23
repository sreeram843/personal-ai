from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from curai.sandbox import SandboxError, resolve_workspace_path, validate_command

PermissionMode = Literal["auto", "ask", "plan"]
MAX_READ_CHARS = 120_000
MAX_OUTPUT_CHARS = 40_000
MAX_LIST_ENTRIES = 200

WRITE_TOOLS = {"write_file", "edit_file"}
SHELL_TOOLS = {"run_command"}
RISKY_TOOLS = WRITE_TOOLS | SHELL_TOOLS


@dataclass
class ToolResult:
    output: str
    error: bool = False


def openai_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files and directories under a path relative to the project root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path (default: .)"},
                        "max_depth": {"type": "integer", "description": "Max depth (default 3)"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a text file, optionally by line range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_code",
                "description": "Search code with ripgrep (rg). Returns matching lines.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string", "description": "Subdirectory or file to search"},
                        "max_results": {"type": "integer"},
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Create or overwrite a file with full content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Replace old_string with new_string in a file (must match exactly once).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Run a shell command in the project root (tests, linters, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "timeout_seconds": {"type": "integer"},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Show git status --short for the project.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_diff",
                "description": "Show git diff (optionally for a path).",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            },
        },
    ]


class ToolExecutor:
    def __init__(
        self,
        workspace: Path,
        *,
        permission_mode: PermissionMode = "ask",
        approve: Callable[[str, dict[str, Any]], bool] | None = None,
    ) -> None:
        self._workspace = workspace.resolve()
        self._permission_mode = permission_mode
        self._approve = approve or (lambda _name, _args: True)

    def requires_approval(self, tool_name: str) -> bool:
        if self._permission_mode == "plan":
            return True
        if self._permission_mode == "auto":
            return tool_name in RISKY_TOOLS
        return tool_name in RISKY_TOOLS or tool_name.startswith("write") or tool_name == "edit_file"

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if self._permission_mode == "plan":
            return ToolResult(output=f"[plan] would run {tool_name} with {arguments}")

        if self.requires_approval(tool_name) and not self._approve(tool_name, arguments):
            return ToolResult(output="ERROR: user denied tool execution", error=True)

        try:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if handler is None:
                return ToolResult(output=f"ERROR: unknown tool '{tool_name}'", error=True)
            return handler(arguments)
        except SandboxError as exc:
            return ToolResult(output=f"ERROR: {exc}", error=True)
        except Exception as exc:
            return ToolResult(output=f"ERROR: {exc}", error=True)

    def _tool_list_directory(self, args: dict[str, Any]) -> ToolResult:
        rel = str(args.get("path") or ".")
        max_depth = int(args.get("max_depth") or 3)
        root = resolve_workspace_path(self._workspace, rel)
        if not root.is_dir():
            return ToolResult(output=f"ERROR: not a directory: {rel}", error=True)
        lines: list[str] = []
        for path in sorted(root.rglob("*")):
            if path.name == ".git":
                continue
            try:
                depth = len(path.relative_to(root).parts)
            except ValueError:
                continue
            if depth > max_depth:
                continue
            if len(lines) >= MAX_LIST_ENTRIES:
                lines.append("... [truncated]")
                break
            suffix = "/" if path.is_dir() else ""
            rel_path = path.relative_to(self._workspace)
            lines.append(f"{rel_path}{suffix}")
        return ToolResult(output="\n".join(lines) or "(empty)")

    def _tool_read_file(self, args: dict[str, Any]) -> ToolResult:
        path = resolve_workspace_path(self._workspace, str(args.get("path") or ""))
        if not path.is_file():
            return ToolResult(output=f"ERROR: file not found: {path}", error=True)
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = int(args.get("start_line") or 1)
        end = int(args.get("end_line") or len(lines))
        start = max(1, start)
        end = min(len(lines), end)
        snippet = "\n".join(f"{i + 1:4d}| {lines[i]}" for i in range(start - 1, end))
        if len(snippet) > MAX_READ_CHARS:
            snippet = snippet[:MAX_READ_CHARS] + "\n[truncated]"
        return ToolResult(output=snippet)

    def _tool_search_code(self, args: dict[str, Any]) -> ToolResult:
        pattern = str(args.get("pattern") or "").strip()
        if not pattern:
            return ToolResult(output="ERROR: pattern is required", error=True)
        search_path = str(args.get("path") or ".")
        target = resolve_workspace_path(self._workspace, search_path)
        max_results = int(args.get("max_results") or 80)
        cmd = ["rg", "--no-heading", "--line-number", "--color=never", "-m", str(max_results), pattern, str(target)]
        try:
            proc = subprocess.run(
                cmd,
                cwd=self._workspace,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            return ToolResult(
                output="ERROR: ripgrep (rg) not found. Install ripgrep or use read_file instead.",
                error=True,
            )
        output = (proc.stdout or proc.stderr or "").strip()
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n[truncated]"
        if proc.returncode not in (0, 1):
            return ToolResult(output=output or f"rg exited {proc.returncode}", error=bool(proc.returncode > 1))
        return ToolResult(output=output or "(no matches)")

    def _tool_write_file(self, args: dict[str, Any]) -> ToolResult:
        path = resolve_workspace_path(self._workspace, str(args.get("path") or ""))
        content = str(args.get("content") or "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(output=f"Wrote {path.relative_to(self._workspace)} ({len(content)} bytes)")

    def _tool_edit_file(self, args: dict[str, Any]) -> ToolResult:
        path = resolve_workspace_path(self._workspace, str(args.get("path") or ""))
        if not path.is_file():
            return ToolResult(output=f"ERROR: file not found: {path}", error=True)
        old = str(args.get("old_string") or "")
        new = str(args.get("new_string") or "")
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            return ToolResult(output=f"ERROR: old_string must match exactly once (found {count} times)", error=True)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return ToolResult(output=f"Edited {path.relative_to(self._workspace)}")

    def _tool_run_command(self, args: dict[str, Any]) -> ToolResult:
        command = str(args.get("command") or "").strip()
        validate_command(command)
        timeout = int(args.get("timeout_seconds") or 120)
        proc = subprocess.run(
            command,
            cwd=self._workspace,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = "\n".join(
            part for part in [f"$ {command}", proc.stdout or "", proc.stderr or "", f"exit code: {proc.returncode}"] if part
        )
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n[truncated]"
        return ToolResult(output=output, error=proc.returncode != 0)

    def _tool_git_status(self, _args: dict[str, Any]) -> ToolResult:
        return self._run_git(["status", "--short"])

    def _tool_git_diff(self, args: dict[str, Any]) -> ToolResult:
        cmd = ["diff"]
        if args.get("path"):
            cmd.append(str(resolve_workspace_path(self._workspace, str(args["path"]))))
        return self._run_git(cmd)

    def _run_git(self, args: list[str]) -> ToolResult:
        proc = subprocess.run(
            ["git", *args],
            cwd=self._workspace,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        output = (proc.stdout or proc.stderr or "").strip()
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n[truncated]"
        return ToolResult(output=output or "(empty)", error=proc.returncode != 0)
