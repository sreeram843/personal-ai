"""Smoke tests for Alembic migration metadata."""

import inspect

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_initial_migration_is_head() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "001_initial"


def test_initial_migration_upgrade_creates_core_tables() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("001_initial")
    assert revision is not None
    source = inspect.getsource(revision.module.upgrade)
    for table in ("users", "conversations", "messages", "documents"):
        assert table in source
