"""Tests for query decomposition before retrieval."""

from __future__ import annotations

import asyncio
from typing import List

from app.core.config import Settings
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.query_decomposition import (
    expand_retrieval_queries,
    heuristic_query_variants,
)
from tests.llm_gateway_stub import LLMGatewayStubMixin


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_heuristic_splits_compound_questions() -> None:
    variants = heuristic_query_variants(
        "Compare kubernetes rollout strategy and rollback procedure?",
        max_queries=3,
    )
    assert variants[0].startswith("Compare kubernetes")
    assert len(variants) >= 2
    assert any("rollback" in item.lower() for item in variants)


def test_heuristic_keeps_single_question() -> None:
    query = "kubernetes deployment rollout strategy"
    assert heuristic_query_variants(query, max_queries=3) == [query]


def test_expand_retrieval_queries_skips_short_queries() -> None:
    variants = asyncio.run(
        expand_retrieval_queries(
            "what is RAG",
            settings=_settings(retrieval_query_decomposition_min_words=4),
        )
    )
    assert variants == ["what is RAG"]


def test_expand_retrieval_queries_uses_llm_variants() -> None:
    class _StubGateway(LLMGatewayStubMixin):
        async def generate(self, *, messages, model: str, options, provider=None):
            return '["k8s deployment rollout", "kubernetes release checklist"]'

    profile = WorkflowModelProfile(
        planner=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        synthesizer=StageModelConfig(provider="ollama", model="qwen2.5:7b"),
        reviewer=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        writer=StageModelConfig(provider="ollama", model="llama3:8b"),
    )
    query = "kubernetes deployment rollout strategy checklist"
    variants = asyncio.run(
        expand_retrieval_queries(
            query,
            settings=_settings(
                retrieval_query_decomposition_enabled=True,
                retrieval_query_decomposition_max_queries=3,
                retrieval_query_decomposition_min_words=4,
            ),
            llm_gateway=_StubGateway(),
            model_profile=profile,
        )
    )
    assert variants[0] == query
    assert len(variants) == 3
    assert "k8s deployment rollout" in variants


def test_expand_retrieval_queries_falls_back_to_heuristic() -> None:
    class _BrokenGateway:
        async def generate(self, *, messages, model: str, options, provider=None):
            raise RuntimeError("planner unavailable")

    profile = WorkflowModelProfile(
        planner=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        synthesizer=StageModelConfig(provider="ollama", model="qwen2.5:7b"),
        reviewer=StageModelConfig(provider="ollama", model="qwen2.5:3b"),
        writer=StageModelConfig(provider="ollama", model="llama3:8b"),
    )
    query = "budget forecast and revenue outlook for Q3"
    variants = asyncio.run(
        expand_retrieval_queries(
            query,
            settings=_settings(retrieval_query_decomposition_min_words=4),
            llm_gateway=_BrokenGateway(),
            model_profile=profile,
        )
    )
    assert variants[0] == query
    assert len(variants) >= 2


def test_expand_retrieval_queries_sync_disabled() -> None:
    variants = asyncio.run(
        expand_retrieval_queries(
            "budget forecast and revenue outlook for Q3",
            settings=_settings(retrieval_query_decomposition_enabled=False),
        )
    )
    assert variants == ["budget forecast and revenue outlook for Q3"]
