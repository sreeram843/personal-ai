"""Ingest archives raw uploads to object storage."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.deps import get_object_storage, get_ollama_client, get_vector_store
from app.main import create_app
from app.services.object_storage import LocalObjectStorage
from tests.conftest import apply_db_auth_overrides


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _RecordingVectorStore:
    def upsert(self, embeddings, documents, *, user_id: str):
        return ["point-1"]


def test_ingest_archives_upload_to_object_storage(db_session, tmp_path: Path) -> None:
    storage = LocalObjectStorage(str(tmp_path / "uploads"))
    app = create_app()
    apply_db_auth_overrides(app, db_session)
    get_object_storage.cache_clear()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_vector_store] = lambda: _RecordingVectorStore()

    client = TestClient(app)
    response = client.post(
        "/ingest",
        json={"documents": [{"text": "Quarterly report", "metadata": {"path": "reports/q1.txt"}}]},
    )

    app.dependency_overrides.clear()
    get_object_storage.cache_clear()

    assert response.status_code == 200
    # One sentence-window chunk plus one per-document summary index point.
    assert response.json()["count"] == 2
    archived = list((tmp_path / "uploads").rglob("*q1.txt"))
    assert archived, "expected archived upload on disk"
    assert archived[0].read_bytes() == b"Quarterly report"
