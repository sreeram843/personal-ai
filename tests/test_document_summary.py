"""Tests for per-document summary index at ingest."""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.schemas.documents import IngestDocument
from app.services.document_summary import (
    DOCUMENT_SUMMARY_CHUNK_TYPE,
    build_document_summary_points,
    build_heuristic_document_summary,
    resolve_ingest_document_id,
    summary_point_id,
)
from app.services.ingest_service import ingest_documents_for_user
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.retrieval_rerank import rerank_and_pack
from app.schemas.chat import RetrievedChunk
from tests.llm_gateway_stub import LLMGatewayStubMixin


def test_build_heuristic_document_summary_uses_leading_sentences() -> None:
    text = "Alpha introduces the topic. Beta adds detail. Gamma concludes."
    summary = build_heuristic_document_summary(text, max_chars=80)
    assert "Alpha introduces" in summary
    assert len(summary) <= 80


def test_summary_point_id_is_stable() -> None:
    assert summary_point_id("notes.md") == summary_point_id("notes.md")
    assert summary_point_id("notes.md") != summary_point_id("other.md")


def test_resolve_ingest_document_id_prefers_path() -> None:
    doc = IngestDocument(text="Body", metadata={"path": "notes.md"})
    assert resolve_ingest_document_id(doc) == "notes.md"


def test_rerank_prefers_document_summaries_for_overview_queries() -> None:
    query = "What are the main themes across my documents?"
    summary = RetrievedChunk(
        id="summary-1",
        score=0.55,
        text="Document summary (report.md): Budget planning and hiring roadmap.",
        metadata={"chunk_type": DOCUMENT_SUMMARY_CHUNK_TYPE},
    )
    chunk = RetrievedChunk(
        id="chunk-1",
        score=0.95,
        text="unrelated picnic schedule and cafeteria menu updates",
        metadata={"chunk_type": "sentence_window"},
    )
    packed = rerank_and_pack(
        query,
        [chunk, summary],
        limit=1,
        prefer_document_summaries=True,
        summary_boost=0.2,
    )
    assert packed[0].id == "summary-1"


def test_build_document_summary_points_uses_llm_when_available() -> None:
    class _StubGateway(LLMGatewayStubMixin):
        async def generate(self, *, messages, model: str, options, provider=None):
            return "Budget planning, hiring roadmap, and Q3 revenue outlook."

    profile = WorkflowModelProfile(
        planner=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        synthesizer=StageModelConfig(provider="ollama", model="qwen2.5:7b"),
        reviewer=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        writer=StageModelConfig(provider="ollama", model="llama3:8b"),
    )
    docs = [
        IngestDocument(
            text="Long body about budget planning and hiring.",
            metadata={"path": "report.md"},
        )
    ]
    points = asyncio.run(
        build_document_summary_points(
            docs,
            settings=Settings(enable_document_summary_index=True),
            user_id="user-1",
            llm_gateway=_StubGateway(),
            model_profile=profile,
        )
    )
    assert len(points) == 1
    assert points[0].metadata["chunk_type"] == DOCUMENT_SUMMARY_CHUNK_TYPE
    assert points[0].metadata["summary_source"] == "llm"
    assert "Budget planning" in points[0].text


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _RecordingVectorStore:
    def __init__(self) -> None:
        self.documents = []

    def upsert(self, embeddings, documents, *, user_id: str):
        self.documents = list(documents)
        return [f"point-{index}" for index, _ in enumerate(documents, start=1)]


def test_ingest_indexes_summary_before_sentence_chunks(db_session) -> None:
    from app.core.auth import DEV_USER_ID, ensure_dev_user
    from app.db.models import Document
    from sqlalchemy import select

    settings = Settings(enable_llamaindex_rag=True, llamaindex_sentence_window_size=1)
    user = ensure_dev_user(db_session, settings)
    vector_store = _RecordingVectorStore()

    count = asyncio.run(
        ingest_documents_for_user(
            db=db_session,
            user=user,
            documents=[
                IngestDocument(
                    text="Sentence one. Sentence two.",
                    metadata={"path": "chunked.md"},
                )
            ],
            settings=settings,
            ollama=_StubOllama(),
            vector_store=vector_store,
            object_storage=None,
        )
    )

    assert count == 3
    assert vector_store.documents[0].metadata["chunk_type"] == DOCUMENT_SUMMARY_CHUNK_TYPE
    assert vector_store.documents[1].text == "Sentence one."
    rows = db_session.scalars(select(Document).where(Document.user_id == DEV_USER_ID)).all()
    assert len(rows) == 2
