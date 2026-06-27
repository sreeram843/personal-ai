"""Tests for multi-query document retrieval."""

from __future__ import annotations

import asyncio
from typing import List

from app.core.config import Settings
from app.services.document_retrieval import retrieve_user_documents
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from tests.llm_gateway_stub import LLMGatewayStubMixin


class _SearchResult:
    def __init__(self, result_id: str, score: float, text: str) -> None:
        self.id = result_id
        self.score = score
        self.payload = {"text": text, "path": f"{result_id}.md"}


class _MultiQueryVectorStore:
    def __init__(self) -> None:
        self.search_calls = 0
        self._results = {
            "variant-a": [
                _SearchResult("shared", 0.55, "kubernetes deployment rollout strategy checklist"),
                _SearchResult("only-a", 0.40, "variant a specific notes"),
            ],
            "variant-b": [
                _SearchResult("shared", 0.80, "kubernetes deployment rollout strategy checklist"),
                _SearchResult("only-b", 0.65, "rollback procedure after failed deployment"),
            ],
        }

    def search(self, vector, *, user_id: str, limit=4, score_threshold=None):
        self.search_calls += 1
        key = "variant-b" if vector[0] > 0.5 else "variant-a"
        return self._results[key][:limit]


class _VariantEmbedClient:
    async def embed(self, inputs):
        vectors: List[List[float]] = []
        for index, _ in enumerate(inputs):
            vectors.append([0.2 if index == 0 else 0.8, 0.1, 0.1])
        return vectors


class _StubGateway(LLMGatewayStubMixin):
    async def generate(self, *, messages, model: str, options, provider=None):
        return '["k8s rollout checklist", "kubernetes rollback procedure"]'


def _profile() -> WorkflowModelProfile:
    stage = StageModelConfig(provider="ollama", model="test-model")
    return WorkflowModelProfile(planner=stage, synthesizer=stage, reviewer=stage, writer=stage)


def test_retrieve_user_documents_merges_multi_query_hits() -> None:
    vector_store = _MultiQueryVectorStore()
    settings = Settings(
        retrieval_wide_top_k=20,
        retrieval_rerank_enabled=True,
        default_top_k=2,
        retrieval_query_decomposition_enabled=True,
        retrieval_query_decomposition_max_queries=3,
        retrieval_query_decomposition_min_words=4,
    )
    result = asyncio.run(
        retrieve_user_documents(
            query="kubernetes deployment rollout strategy checklist",
            user_id="user-1",
            embed_client=_VariantEmbedClient(),
            vector_store=vector_store,
            settings=settings,
            pack_limit=2,
            llm_gateway=_StubGateway(),
            model_profile=_profile(),
        )
    )

    assert vector_store.search_calls == 3
    assert len(result.query_variants) == 3
    ids = {item.id for item in result.sources}
    assert "shared" in ids
    assert result.sources[0].id == "shared"
    assert result.sources[0].score == 0.80
    assert len(result.sources) == 2
