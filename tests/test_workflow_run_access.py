"""Tests for workflow run access helpers."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.auth import DEV_USER_ID, ensure_dev_user
from app.core.config import Settings
from app.db.models import User
from app.services.conversation_store import create_conversation
from app.services.run_store import RunStore
from app.services.workflow_run_access import require_workflow_run, verify_conversation_owned_by_user


def test_verify_conversation_owned_by_user_rejects_foreign_conversation(db_session) -> None:
    settings = Settings(auth_disabled=True, jwt_secret="test", database_url="sqlite://")
    dev_user = ensure_dev_user(db_session, settings)
    other = User(email="other@example.com", display_name="Other")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    foreign_conv = create_conversation(db_session, other, title="Foreign")

    with pytest.raises(HTTPException) as exc:
        verify_conversation_owned_by_user(db_session, dev_user, str(foreign_conv.id))
    assert exc.value.status_code == 404


def test_require_workflow_run_scopes_to_user(tmp_path) -> None:
    store = RunStore(storage_path=str(tmp_path / "runs"))
    run = store.create_run(mode="workflow", conversation_id="conv-1", user_id=str(DEV_USER_ID))

    class _User:
        id = DEV_USER_ID

    loaded = require_workflow_run(store, run_id=run.run_id, user=_User())
    assert loaded.run_id == run.run_id

    class _Other:
        id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    with pytest.raises(HTTPException) as exc:
        require_workflow_run(store, run_id=run.run_id, user=_Other())
    assert exc.value.status_code == 404
