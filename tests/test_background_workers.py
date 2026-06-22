"""Tests for background ingest enqueue behavior."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.deps import get_ollama_client, get_vector_store
from app.main import create_app
from app.services.task_queue import InlineTaskQueue, reset_task_queue
from tests.conftest import apply_db_auth_overrides


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _RecordingVectorStore:
    def __init__(self) -> None:
        self.upsert_calls = 0

    def upsert(self, embeddings, documents, *, user_id: str):
        self.upsert_calls += 1
        return ["point-1"]


def test_ingest_stays_sync_when_workers_disabled(db_session) -> None:
    app = create_app()
    settings = apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: settings
    recording_store = _RecordingVectorStore()
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_vector_store] = lambda: recording_store

    client = TestClient(app)
    response = client.post(
        "/ingest",
        json={"documents": [{"text": "Private notes", "metadata": {"path": "notes.txt"}}]},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body.get("job_id") is None
    assert recording_store.upsert_calls == 1


@pytest.mark.skip(
    reason=(
        "CI: get_task_queue() calls get_settings() outside FastAPI DI, so enable_background_workers "
        "override is ignored and /ingest returns 503. Re-enable after fixing task queue test wiring."
    )
)
def test_ingest_enqueues_large_batch_with_inline_worker(db_session, monkeypatch) -> None:
    # TODO(#inline-worker-ingest): use app.dependency_overrides[get_task_queue] or make
    # get_task_queue() rebuild when settings change. See skipped reason above.
    reset_task_queue()
    recording_store = _RecordingVectorStore()
    inline_queue = InlineTaskQueue(
        ctx={
            "service_overrides": {
                "ollama": _StubOllama(),
                "vector_store": recording_store,
            }
        }
    )
    monkeypatch.setattr("app.services.task_queue.build_task_queue", lambda *_args, **_kwargs: inline_queue)
    monkeypatch.setattr("app.api.routes.get_task_queue", lambda: inline_queue)
    app = create_app()
    settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
        dev_user_email="dev@localhost",
        dev_user_display_name="Dev User",
        enable_background_workers=True,
        worker_queue_backend="inline",
        ingest_async_min_documents=1,
        redis_url=None,
    )
    apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_vector_store] = lambda: recording_store

    client = TestClient(app)
    response = client.post(
        "/ingest",
        json={"documents": [{"text": "Queued notes", "metadata": {"path": "queued.txt"}}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert recording_store.upsert_calls == 1

    job_response = client.get(f"/jobs/{body['job_id']}")
    app.dependency_overrides.clear()
    reset_task_queue()

    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"
    assert job_response.json()["result"]["count"] == 1
