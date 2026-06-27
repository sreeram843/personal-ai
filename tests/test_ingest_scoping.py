"""Tests for scoped document ingest."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_ollama_client, get_vector_store
from app.main import create_app
from tests.conftest import apply_db_auth_overrides


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _RecordingVectorStore:
    def __init__(self) -> None:
        self.last_user_id: str | None = None
        self.last_documents = []

    def upsert(self, embeddings, documents, *, user_id: str):
        self.last_user_id = user_id
        self.last_documents = list(documents)
        return [f"point-{index + 1}" for index in range(len(documents))]


def test_ingest_scopes_documents_to_current_user(db_session) -> None:
    app = create_app()
    apply_db_auth_overrides(app, db_session)
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
    # One sentence-window chunk plus one per-document summary index point.
    assert response.json()["count"] == 2
    assert recording_store.last_user_id is not None
    chunk_texts = [
        doc.text
        for doc in recording_store.last_documents
        if doc.metadata.get("chunk_type") != "document_summary"
    ]
    assert any("Private notes" in text for text in chunk_texts)

    from app.core.auth import DEV_USER_ID
    from app.db.models import Document
    from sqlalchemy import select

    rows = db_session.scalars(select(Document).where(Document.user_id == DEV_USER_ID)).all()
    assert len(rows) == 1
    assert rows[0].qdrant_point_id == "point-2"
