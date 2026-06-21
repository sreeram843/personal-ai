"""Workflow run tenant isolation tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.auth import DEV_USER_ID, ensure_dev_user
from app.core.config import Settings, get_settings
from app.core.deps import get_run_store
from app.core.security import create_access_token
from app.db.models import User
from app.main import create_app
from app.schemas.run import RunStatus
from app.services.conversation_store import create_conversation
from app.services.run_store import RunStore
from tests.conftest import apply_db_auth_overrides


def _make_client(db_session, tmp_path: Path, *, auth_disabled: bool) -> tuple[TestClient, RunStore, Settings]:
    app = create_app()
    settings = apply_db_auth_overrides(app, db_session)
    settings = settings.model_copy(update={"auth_disabled": auth_disabled})
    app.dependency_overrides[get_settings] = lambda: settings
    store = RunStore(storage_path=str(tmp_path / "runs"))
    app.dependency_overrides[get_run_store] = lambda: store
    return TestClient(app), store, settings


def test_workflow_runs_are_isolated_between_users(db_session, tmp_path: Path) -> None:
    client, store, settings = _make_client(db_session, tmp_path, auth_disabled=False)
    user_b = User(email="bob@example.com", display_name="Bob")
    db_session.add(user_b)
    db_session.commit()
    db_session.refresh(user_b)

    dev_user = ensure_dev_user(db_session, settings)
    conv_a = create_conversation(db_session, dev_user, title="A")
    conv_b = create_conversation(db_session, user_b, title="B")

    run_a = store.create_run(mode="workflow", conversation_id=str(conv_a.id), user_id=str(DEV_USER_ID))
    store.create_run(mode="workflow", conversation_id=str(conv_b.id), user_id=str(user_b.id))
    store.update_run_status(run_a.run_id, RunStatus.IN_PROGRESS, user_id=str(DEV_USER_ID))

    dev_token = create_access_token(user_id=DEV_USER_ID, settings=settings)
    bob_token = create_access_token(user_id=user_b.id, settings=settings)

    assert client.get(f"/workflow_runs/{run_a.run_id}", headers={"Authorization": f"Bearer {dev_token}"}).status_code == 200
    assert client.get(
        f"/workflow_runs/{run_a.run_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    ).status_code == 404
    assert client.get(
        "/workflow_runs",
        params={"conversation_id": str(conv_a.id)},
        headers={"Authorization": f"Bearer {bob_token}"},
    ).status_code == 404
