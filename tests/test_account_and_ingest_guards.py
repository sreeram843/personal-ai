from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.deps import get_ollama_client, get_vector_store
from app.main import create_app
from tests.conftest import apply_db_auth_overrides


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _RecordingVectorStore:
    def upsert(self, embeddings, documents, *, user_id: str):
        return ["point-1"]

    def delete_for_user(self, user_id: str) -> None:
        return None

    def ensure_collection(self) -> None:
        return None

    def search(self, *args, **kwargs):
        return []


def _app_with_settings(db_session, settings: Settings):
    app = create_app()
    apply_db_auth_overrides(app, db_session)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_vector_store] = lambda: _RecordingVectorStore()
    return app


def test_ingest_rejects_oversized_document(db_session) -> None:
    settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
        ingest_max_document_bytes=32,
        ingest_max_batch_bytes=10_000,
        ingest_allowed_extensions=".txt,.md",
    )
    app = _app_with_settings(db_session, settings)
    client = TestClient(app)
    response = client.post(
        "/ingest",
        json={"documents": [{"text": "x" * 64, "metadata": {"path": "notes.txt"}}]},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 400
    assert "max size" in response.text.lower()


def test_ingest_rejects_disallowed_extension(db_session) -> None:
    settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
        ingest_allowed_extensions=".txt,.md",
    )
    app = _app_with_settings(db_session, settings)
    client = TestClient(app)
    response = client.post(
        "/ingest",
        json={"documents": [{"text": "hello", "metadata": {"path": "notes.exe"}}]},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 400
    assert ".exe" in response.text


def test_ingest_files_accepts_pdf(db_session) -> None:
    settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
        ingest_allowed_extensions=".txt,.md,.pdf",
        enable_llamaindex_rag=False,
    )
    app = _app_with_settings(db_session, settings)
    client = TestClient(app)
    pdf_bytes = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length 68 >>stream
BT /F1 12 Tf 50 100 Td (CurAI PDF ingest marker) Tj ET
endstream
endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000384 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
461
%%EOF
"""
    response = client.post(
        "/ingest/files",
        files=[("files", ("quarterly.pdf", pdf_bytes, "application/pdf"))],
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    assert response.json().get("count", 0) >= 1


def test_ingest_files_rejects_oversized_upload(db_session) -> None:
    """
    /ingest/files bounds the raw (pre-extraction) upload separately from
    ingest_max_document_bytes, which caps extracted text — see
    ingest_max_upload_bytes in app/core/config.py.
    """
    settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
        ingest_allowed_extensions=".txt,.md,.pdf",
        ingest_max_upload_bytes=16,
    )
    app = _app_with_settings(db_session, settings)
    client = TestClient(app)
    response = client.post(
        "/ingest/files",
        files=[("files", ("notes.txt", b"x" * 64, "text/plain"))],
    )
    app.dependency_overrides.clear()
    assert response.status_code == 400
    assert "max upload size" in response.text.lower()


def test_export_account_data(db_session) -> None:
    settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
    )
    app = _app_with_settings(db_session, settings)
    client = TestClient(app)
    response = client.get("/auth/me/export")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert "exported_at" in body
    assert "conversations" in body
    assert body["user"]["email"] == "dev@localhost"


def test_delete_account_blocked_when_auth_disabled(db_session) -> None:
    settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
    )
    app = _app_with_settings(db_session, settings)
    client = TestClient(app)
    response = client.delete("/auth/me")
    app.dependency_overrides.clear()
    assert response.status_code == 400
