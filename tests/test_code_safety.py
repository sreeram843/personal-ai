"""Tests for the Agent Lab code safety denylist (used by Phases 4 and 7)."""

from __future__ import annotations

from app.services.learn_agents._code_safety import check_code_safety


def test_allows_pure_computation():
    code = "def add(a, b):\n    return a + b\n"
    assert check_code_safety(code) is None


def test_rejects_banned_module_import():
    code = "import os\n\ndef f():\n    return os.getcwd()\n"
    assert "os" in check_code_safety(code)


def test_rejects_banned_from_import():
    code = "from subprocess import run\n\ndef f():\n    return run(['ls'])\n"
    assert "subprocess" in check_code_safety(code)


def test_rejects_eval():
    code = "def f(x):\n    return eval(x)\n"
    assert "eval" in check_code_safety(code)


def test_rejects_dunder_import():
    code = "def f():\n    return __import__('os')\n"
    assert "__import__" in check_code_safety(code)


def test_rejects_open_builtin():
    code = "def f():\n    return open('/etc/passwd').read()\n"
    assert "open" in check_code_safety(code)


def test_reports_syntax_errors():
    code = "def f(:\n    pass\n"
    error = check_code_safety(code)
    assert error is not None and "syntax error" in error
