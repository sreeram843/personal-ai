from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.auth import DEV_USER_ID, ensure_dev_user
from app.core.config import Settings, get_settings
from app.core.deps import get_run_store
from app.db.models import User
from app.main import create_app
from app.schemas.run import RunStatus
from app.services.conversation_store import create_conversation
from app.services.run_store import RunStore
from tests.conftest import apply_db_auth_overrides


def _make_client(db_session, tmp_path: Path) -> tuple[TestClient, RunStore, Settings]:
    app = create_app()
    settings = apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: settings
    store = RunStore(storage_path=str(tmp_path / "runs"))
    app.dependency_overrides[get_run_store] = lambda: store
    return TestClient(app), store, settings


def test_workflow_run_endpoints_lifecycle(db_session, tmp_path: Path) -> None:
    client, store, settings = _make_client(db_session, tmp_path)
    dev_user = ensure_dev_user(db_session, settings)
    conversation = create_conversation(db_session, dev_user, title="Workflow test")

    create_resp = client.post(
        "/workflow_runs",
        json={"mode": "workflow", "conversation_id": str(conversation.id)},
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    run_id = created["run_id"]
    assert created["status"] == "pending"
    assert created["user_id"] == str(DEV_USER_ID)

    get_resp = client.get(f"/workflow_runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["run_id"] == run_id

    list_resp = client.get("/workflow_runs", params={"conversation_id": str(conversation.id)})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    pause_conflict = client.post(f"/workflow_runs/{run_id}/pause")
    assert pause_conflict.status_code == 409

    store.update_run_status(run_id, RunStatus.IN_PROGRESS, user_id=str(DEV_USER_ID))
    pause_resp = client.post(f"/workflow_runs/{run_id}/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "paused"

    resume_resp = client.post(f"/workflow_runs/{run_id}/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "resuming"

    cancel_resp = client.post(f"/workflow_runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    resume_conflict = client.post(f"/workflow_runs/{run_id}/resume")
    assert resume_conflict.status_code == 409


def test_get_missing_workflow_run_returns_404(db_session, tmp_path: Path) -> None:
    client, _, _ = _make_client(db_session, tmp_path)
    resp = client.get("/workflow_runs/non-existent")
    assert resp.status_code == 404
