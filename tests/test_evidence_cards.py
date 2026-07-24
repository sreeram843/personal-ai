"""Tests for compact evidence cards and writer-stage context packing."""

from __future__ import annotations

import asyncio

from app.schemas.chat import RetrievedChunk
from app.services.evidence_cards import (
    build_evidence_card,
    extract_cited_evidence_ids,
    format_writer_evidence_context,
)
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.orchestrated_chat import OrchestratedChatService
from tests.llm_gateway_stub import LLMGatewayStubMixin


def test_extract_cited_evidence_ids() -> None:
    draft = "Revenue grew 12% [[evidence:doc-42]] per the report [[evidence:web-1]]."
    assert extract_cited_evidence_ids(draft) == {"doc-42", "web-1"}
    assert extract_cited_evidence_ids("No markers here.") == set()


def test_build_evidence_card_truncates_long_text() -> None:
    long_text = "Sentence one is here. " + ("word " * 200)
    source = RetrievedChunk(
        id="doc-1",
        score=0.91,
        text=long_text,
        metadata={"path": "docs/design.md", "trust_lane": "retrieved"},
    )
    card = build_evidence_card(source, max_chars=120)
    assert "[evidence:doc-1]" in card
    assert "docs/design.md" in card
    assert "retrieved" in card
    assert len(card) < len(long_text)


def test_format_writer_evidence_context_prefers_cited_ids() -> None:
    registry = {
        "doc-1": RetrievedChunk(id="doc-1", score=0.9, text="Internal only.", metadata={"path": "a.md"}),
        "doc-2": RetrievedChunk(id="doc-2", score=0.8, text="Should be omitted.", metadata={"path": "b.md"}),
    }
    context = format_writer_evidence_context(registry, cited_ids=["doc-1"])
    assert "doc-1" in context
    assert "Internal only" in context
    assert "Should be omitted" not in context


class _CapturingGateway(LLMGatewayStubMixin):
    def __init__(self) -> None:
        self.writer_prompt = ""

    async def generate(self, *, messages, model: str, options, provider=None):
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        user_text = "\n".join(item["content"] for item in messages if item["role"] == "user")
        if "You are the synthesizer." in system_text:
            return "Draft with [[evidence:doc-1]] citation."
        if "You are the reviewer." in system_text:
            return "Looks good."
        if "You are the writer." in system_text:
            self.writer_prompt = user_text
            return "Final answer."
        return "ok"


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _SearchResult:
    def __init__(self, result_id: str, score: float, payload: dict):
        self.id = result_id
        self.score = score
        self.payload = payload


class _StubVectorStore:
    def search(self, vector, *, user_id: str, limit=4, score_threshold=None, query_text=None, hybrid=False):
        return [
            _SearchResult(
                "doc-1",
                0.91,
                {
                    "text": (
                        "Design overview: modular orchestration with retrieval. "
                        + ("TAIL_ONLY_DETAIL_NOT_FOR_WRITER " * 40)
                    ),
                    "path": "docs/design.md",
                    "name": "Design Doc",
                },
            )
        ]


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


def test_writer_uses_compact_evidence_cards_not_full_chunks() -> None:
    gateway = _CapturingGateway()
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=gateway,
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )

    asyncio.run(
        service.run_mode(
            mode="rag",
            query="What does the design doc say?",
            system_prompt="You are helpful.",
            chat_history=[],
            conversation_id=None,
            user_id="user-1",
            top_k=4,
            score_threshold=None,
            options={"progressive_disclosure_level": "compact"},
            use_rag=True,
            include_trace=False,
            persist_memory=False,
            max_steps=6,
        )
    )

    assert gateway.writer_prompt
    assert "TAIL_ONLY_DETAIL_NOT_FOR_WRITER" not in gateway.writer_prompt
    assert "[evidence:doc-1]" in gateway.writer_prompt
    assert "Evidence cards" in gateway.writer_prompt


class _StubVectorStoreFull:
    def search(self, vector, *, user_id: str, limit=4, score_threshold=None, query_text=None, hybrid=False):
        return [
            _SearchResult(
                "doc-1",
                0.91,
                {
                    "text": (
                        "Design overview: modular orchestration with retrieval. "
                        + ("TAIL_ONLY_DETAIL_NOT_FOR_WRITER " * 40)
                    ),
                    "path": "docs/design.md",
                    "name": "Design Doc",
                },
            )
        ]


def test_writer_uses_full_context_when_disclosure_level_full() -> None:
    gateway = _CapturingGateway()
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=gateway,
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStoreFull(),
        memory_store=_StubWorkflowMemoryStore(),
    )

    asyncio.run(
        service.run_mode(
            mode="rag",
            query="What does the design doc say?",
            system_prompt="You are helpful.",
            chat_history=[],
            conversation_id=None,
            user_id="user-1",
            top_k=4,
            score_threshold=None,
            options={"progressive_disclosure_level": "full"},
            use_rag=True,
            include_trace=False,
            persist_memory=False,
            max_steps=6,
        )
    )

    assert "TAIL_ONLY_DETAIL_NOT_FOR_WRITER" in gateway.writer_prompt
    assert "Internal document context:" in gateway.writer_prompt
