"""Tests for wide retrieval, hybrid rerank, and MMR packing."""

from __future__ import annotations

import asyncio
from typing import List

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.orchestrated_chat import OrchestratedChatService
from tests.llm_gateway_stub import LLMGatewayStubMixin
from app.services.retrieval_rerank import (
    lexical_overlap_score,
    rerank_and_pack,
    wide_retrieval_limit,
)


def _chunk(chunk_id: str, score: float, text: str) -> RetrievedChunk:
    return RetrievedChunk(id=chunk_id, score=score, text=text, metadata={"path": f"{chunk_id}.md"})


def test_lexical_overlap_score_prefers_matching_terms() -> None:
    query = "kubernetes deployment rollout strategy"
    high = _chunk("a", 0.5, "kubernetes deployment rollout strategy for production")
    low = _chunk("b", 0.5, "unrelated cooking recipe for pasta")
    assert lexical_overlap_score(query, high.text) > lexical_overlap_score(query, low.text)


def test_rerank_and_pack_prefers_lexically_relevant_despite_lower_vector_score() -> None:
    query = "budget forecast Q3 revenue"
    candidates = [
        _chunk("weak-vector", 0.95, "generic company overview and history"),
        _chunk("strong-lexical", 0.55, "budget forecast Q3 revenue increased twelve percent"),
        _chunk("noise-1", 0.90, "office cafeteria menu updates"),
        _chunk("noise-2", 0.88, "parking policy reminder for employees"),
    ]
    packed = rerank_and_pack(query, candidates, limit=2)
    assert [item.id for item in packed] == ["strong-lexical", "weak-vector"]


def test_rerank_and_pack_applies_mmr_diversity() -> None:
    query = "deployment checklist"
    candidates = [
        _chunk("a", 0.95, "deployment checklist step one verify config"),
        _chunk("b", 0.94, "deployment checklist step one verify config duplicate"),
        _chunk("c", 0.70, "rollback procedure after failed deployment"),
    ]
    packed = rerank_and_pack(query, candidates, limit=2)
    ids = {item.id for item in packed}
    assert "c" in ids
    assert len(ids) == 2


def test_wide_retrieval_limit() -> None:
    assert wide_retrieval_limit(pack_limit=4, wide_top_k=20, rerank_enabled=True) == 20
    assert wide_retrieval_limit(pack_limit=8, wide_top_k=20, rerank_enabled=True) == 20
    assert wide_retrieval_limit(pack_limit=4, wide_top_k=20, rerank_enabled=False) == 4


class _RecordingVectorStore:
    def __init__(self, results: List[object]) -> None:
        self.results = results
        self.last_limit: int | None = None

    def search(self, vector, *, user_id: str, limit=4, score_threshold=None):
        self.last_limit = limit
        return self.results


class _SearchResult:
    def __init__(self, result_id: str, score: float, text: str) -> None:
        self.id = result_id
        self.score = score
        self.payload = {"text": text, "path": f"{result_id}.md"}


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _StubGateway(LLMGatewayStubMixin):
    async def generate(self, *, messages, model: str, options, provider=None):
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        if "You are the synthesizer." in system_text:
            return "Draft [[evidence:target]]."
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


def test_retriever_fetches_wide_then_packs(monkeypatch) -> None:
    vector_store = _RecordingVectorStore(
        [
            _SearchResult("noise-1", 0.99, "unrelated annual picnic schedule"),
            _SearchResult("noise-2", 0.98, "office holiday calendar details"),
            _SearchResult("target", 0.60, "kubernetes deployment rollout strategy checklist"),
            _SearchResult("noise-3", 0.97, "team building event planning notes"),
        ]
    )
    monkeypatch.setattr(
        "app.services.orchestrated_chat.get_settings",
        lambda: Settings(
            retrieval_wide_top_k=20,
            retrieval_rerank_enabled=True,
            default_top_k=4,
            retrieval_query_decomposition_enabled=False,
        ),
    )

    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=_StubGateway(),
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=vector_store,
        memory_store=_StubWorkflowMemoryStore(),
    )

    result = asyncio.run(
        service.run_mode(
            mode="rag",
            query="kubernetes deployment rollout strategy",
            system_prompt="You are helpful.",
            chat_history=[],
            conversation_id=None,
            user_id="user-1",
            top_k=1,
            score_threshold=None,
            options={"progressive_disclosure_level": "compact", "require_evidence_markers": False},
            use_rag=True,
            include_trace=False,
            persist_memory=False,
            max_steps=6,
        )
    )

    assert vector_store.last_limit == 20
    assert len(result.sources) == 1
    assert result.sources[0].id == "target"
    assert "rollout strategy" in result.sources[0].text
