"""Smoke tests for Alembic migration metadata."""

import inspect

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_head_is_latest() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "002_conversation_pin"


def test_initial_migration_upgrade_creates_core_tables() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("001_initial")
    assert revision is not None
    source = inspect.getsource(revision.module.upgrade)
    for table in ("users", "conversations", "messages", "documents"):
        assert table in source


def test_conversation_pin_migration_adds_pinned_at() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("002_conversation_pin")
    assert revision is not None
    source = inspect.getsource(revision.module.upgrade)
    assert "pinned_at" in source
