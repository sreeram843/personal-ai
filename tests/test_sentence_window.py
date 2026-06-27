"""Tests for sentence-window ingest and retrieval expansion."""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.services.ingest_service import ingest_documents_for_user
from app.services.orchestrated_chat import OrchestratedChatService
from tests.llm_gateway_stub import LLMGatewayStubMixin
from app.services.sentence_window import (
    build_sentence_window_chunks,
    resolve_retrieval_text,
    stored_documents_from_sentence_chunks,
)
from app.schemas.documents import IngestDocument
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile


def test_build_sentence_window_chunks_creates_context_windows() -> None:
    text = "Alpha starts. Beta adds detail. Gamma continues. Delta ends."
    chunks = build_sentence_window_chunks(text, {"path": "doc.md"}, window_size=1)
    assert len(chunks) == 4
    assert chunks[1].sentence == "Beta adds detail."
    assert "Alpha starts." in chunks[1].window
    assert "Gamma continues." in chunks[1].window
    assert chunks[1].metadata["path"] == "doc.md"


def test_resolve_retrieval_text_prefers_window_metadata() -> None:
    payload = {
        "text": "Short sentence.",
        "window": "Short sentence. Neighbor sentence adds missing context.",
    }
    assert resolve_retrieval_text(payload).startswith("Short sentence. Neighbor")


def test_stored_documents_embed_sentences_but_keep_window_metadata() -> None:
    docs = [
        IngestDocument(
            text="First point. Second point with details.",
            metadata={"path": "notes.md"},
        )
    ]
    stored = stored_documents_from_sentence_chunks(
        docs,
        user_id="user-1",
        window_size=1,
        prefer_llamaindex=False,
    )
    assert len(stored) == 2
    assert stored[0].text == "First point."
    assert "Second point" in stored[0].metadata["window"]
    assert stored[0].metadata["user_id"] == "user-1"


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _RecordingVectorStore:
    def __init__(self) -> None:
        self.documents = []

    def upsert(self, embeddings, documents, *, user_id: str):
        self.documents = list(documents)
        return [f"point-{index}" for index, _ in enumerate(documents, start=1)]


def test_ingest_service_uses_sentence_window_chunks(db_session) -> None:
    from app.core.auth import DEV_USER_ID, ensure_dev_user
    from app.db.models import Document
    from sqlalchemy import select

    settings = Settings(
        enable_llamaindex_rag=True,
        llamaindex_sentence_window_size=1,
        enable_document_summary_index=False,
    )
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

    assert count == 2
    assert vector_store.documents[0].text == "Sentence one."
    assert "Sentence two." in vector_store.documents[0].metadata["window"]
    rows = db_session.scalars(select(Document).where(Document.user_id == DEV_USER_ID)).all()
    assert len(rows) == 2


class _SearchResult:
    def __init__(self, result_id: str, score: float, payload: dict):
        self.id = result_id
        self.score = score
        self.payload = payload


class _StubVectorStore:
    def search(self, vector, *, user_id: str, limit=4, score_threshold=None):
        return [
            _SearchResult(
                "chunk-1",
                0.88,
                {
                    "text": "Beta adds detail.",
                    "window": "Alpha starts. Beta adds detail. Gamma continues.",
                    "path": "doc.md",
                },
            )
        ]


class _StubGateway(LLMGatewayStubMixin):
    async def generate(self, *, messages, model: str, options, provider=None):
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        if "You are the synthesizer." in system_text:
            return "Draft [[evidence:chunk-1]]."
        if "You are the reviewer." in system_text:
            return "ok"
        if "You are the writer." in system_text:
            return "Final"
        return "ok"


class _StubWebSearch:
    async def search_with_page_excerpts(self, query: str):
        return []


class _StubWorkflowMemoryStore:
    async def get_summary(self, conversation_id: str, *, user_id: str | None = None, limit: int = 6) -> str:
        return ""

    async def append_entries(self, conversation_id: str, entries, *, user_id: str | None = None):
        return None


def _stub_model_profile() -> WorkflowModelProfile:
    stage = StageModelConfig(provider="ollama", model="test-model")
    return WorkflowModelProfile(planner=stage, synthesizer=stage, reviewer=stage, writer=stage)


def test_retriever_expands_sentence_window_context() -> None:
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=_StubGateway(),
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )

    result = asyncio.run(
        service.run_mode(
            mode="rag",
            query="What does beta add?",
            system_prompt="You are helpful.",
            chat_history=[],
            conversation_id=None,
            user_id="user-1",
            top_k=1,
            score_threshold=None,
            options={"require_evidence_markers": False},
            use_rag=True,
            include_trace=False,
            persist_memory=False,
            max_steps=6,
        )
    )

    assert result.sources
    assert "Gamma continues." in result.sources[0].text
    assert result.sources[0].text.startswith("Alpha starts.")
