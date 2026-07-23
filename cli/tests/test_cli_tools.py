from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from curai.sandbox import SandboxError, resolve_workspace_path, validate_command
from curai.tools.executor import ToolExecutor


def test_resolve_workspace_path_blocks_escape(tmp_path: Path) -> None:
    inside = tmp_path / "proj"
    inside.mkdir()
    resolved = resolve_workspace_path(inside, "src/foo.py")
    assert resolved == (inside / "src/foo.py").resolve()
    with pytest.raises(SandboxError):
        resolve_workspace_path(inside, "../../etc/passwd")


def test_validate_command_blocks_rm() -> None:
    with pytest.raises(SandboxError):
        validate_command("rm -rf .")


def test_read_and_edit_file(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    target.write_text("hello world\n", encoding="utf-8")
    executor = ToolExecutor(tmp_path, permission_mode="auto")
    read = executor.execute("read_file", {"path": "hello.txt"})
    assert "hello world" in read.output
    edit = executor.execute(
        "edit_file",
        {"path": "hello.txt", "old_string": "world", "new_string": "curai"},
    )
    assert not edit.error
    assert target.read_text(encoding="utf-8") == "hello curai\n"


def test_plan_mode_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "nope.txt"
    executor = ToolExecutor(tmp_path, permission_mode="plan")
    result = executor.execute("write_file", {"path": "nope.txt", "content": "x"})
    assert "[plan]" in result.output
    assert not target.exists()
