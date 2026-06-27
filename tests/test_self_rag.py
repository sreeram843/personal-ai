"""Tests for Self-RAG retrieval retry loop."""

from __future__ import annotations

import asyncio
from typing import List

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk
from app.services.document_retrieval import DocumentRetrievalResult
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.self_rag import (
    assess_retrieval_sufficiency,
    heuristic_assess_retrieval,
    retrieve_user_documents_with_self_rag,
)


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def _chunk(chunk_id: str, score: float, text: str) -> RetrievedChunk:
    return RetrievedChunk(id=chunk_id, score=score, text=text, metadata={"path": f"{chunk_id}.md"})


def test_heuristic_assess_retrieval_accepts_strong_match() -> None:
    sources = [_chunk("a", 0.82, "kubernetes deployment rollout strategy checklist")]
    assessment = heuristic_assess_retrieval(
        "kubernetes deployment rollout strategy",
        sources,
        settings=_settings(),
    )
    assert assessment.sufficient is True


def test_heuristic_assess_retrieval_rejects_weak_match() -> None:
    sources = [_chunk("a", 0.90, "office picnic schedule and cafeteria menu")]
    assessment = heuristic_assess_retrieval(
        "kubernetes deployment rollout strategy",
        sources,
        settings=_settings(),
    )
    assert assessment.sufficient is False
    assert assessment.follow_up_query


def test_retrieve_with_self_rag_retries_on_weak_first_hop(monkeypatch) -> None:
    calls: List[str] = []

    async def _fake_retrieve(*, query: str, **kwargs):
        calls.append(query)
        if query == "kubernetes deployment rollout strategy":
            return DocumentRetrievalResult(
                sources=[_chunk("noise", 0.95, "office picnic schedule and cafeteria menu")],
                query_variants=[query],
                candidates_considered=4,
            )
        return DocumentRetrievalResult(
            sources=[_chunk("target", 0.70, "kubernetes deployment rollout strategy checklist")],
            query_variants=[query],
            candidates_considered=3,
        )

    monkeypatch.setattr("app.services.self_rag.retrieve_user_documents", _fake_retrieve)

    class _StubEmbed:
        async def embed(self, inputs):
            return [[0.1, 0.2, 0.3] for _ in inputs]

    class _StubStore:
        def search(self, *args, **kwargs):
            return []

    result = asyncio.run(
        retrieve_user_documents_with_self_rag(
            query="kubernetes deployment rollout strategy",
            user_id="user-1",
            embed_client=_StubEmbed(),
            vector_store=_StubStore(),
            settings=_settings(
                enable_self_rag_retry=True,
                self_rag_max_hops=2,
                self_rag_use_llm_judge=False,
            ),
            pack_limit=1,
        )
    )

    assert len(calls) == 2
    assert result.retrieval_hops == 2
    assert result.sources[0].id == "target"


def test_retrieve_with_self_rag_stops_after_strong_first_hop(monkeypatch) -> None:
    calls: List[str] = []

    async def _fake_retrieve(*, query: str, **kwargs):
        calls.append(query)
        return DocumentRetrievalResult(
            sources=[_chunk("target", 0.82, "kubernetes deployment rollout strategy checklist")],
            query_variants=[query],
            candidates_considered=2,
        )

    monkeypatch.setattr("app.services.self_rag.retrieve_user_documents", _fake_retrieve)

    class _StubEmbed:
        async def embed(self, inputs):
            return [[0.1, 0.2, 0.3] for _ in inputs]

    class _StubStore:
        def search(self, *args, **kwargs):
            return []

    result = asyncio.run(
        retrieve_user_documents_with_self_rag(
            query="kubernetes deployment rollout strategy",
            user_id="user-1",
            embed_client=_StubEmbed(),
            vector_store=_StubStore(),
            settings=_settings(enable_self_rag_retry=True, self_rag_max_hops=2),
            pack_limit=1,
        )
    )

    assert len(calls) == 1
    assert result.retrieval_hops == 1


def test_llm_judge_can_request_follow_up_query() -> None:
    class _JudgeGateway:
        async def generate(self, *, messages, model: str, options, provider=None):
            return '{"sufficient": false, "follow_up_query": "rollback procedure after failed deployment"}'

    profile = WorkflowModelProfile(
        planner=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        synthesizer=StageModelConfig(provider="ollama", model="qwen2.5:7b"),
        reviewer=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        writer=StageModelConfig(provider="ollama", model="llama3:8b"),
    )
    weak_sources = [_chunk("noise", 0.95, "office picnic schedule and cafeteria menu")]
    assessment = asyncio.run(
        assess_retrieval_sufficiency(
            "kubernetes deployment rollout strategy",
            weak_sources,
            settings=_settings(self_rag_use_llm_judge=True),
            attempted_queries=["kubernetes deployment rollout strategy"],
            llm_gateway=_JudgeGateway(),
            model_profile=profile,
        )
    )
    assert assessment.sufficient is False
    assert "rollback" in assessment.follow_up_query.lower()
