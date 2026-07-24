"""Tests for citation preservation into the final user-facing answer."""

from __future__ import annotations

import asyncio

from app.schemas.chat import RetrievedChunk
from app.services.citations import (
    RAG_CITATION_RULE,
    ensure_answer_preserves_citations,
    evidence_label,
    replace_evidence_markers_with_path_citations,
)
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.orchestrated_chat import OrchestratedChatService
from tests.llm_gateway_stub import LLMGatewayStubMixin


def _chunk(evidence_id: str, path: str, text: str = "Relevant passage.") -> RetrievedChunk:
    return RetrievedChunk(
        id=evidence_id,
        score=0.95,
        text=text,
        metadata={"path": path, "name": path.rsplit("/", 1)[-1]},
    )


def test_replace_evidence_markers_with_path_citations() -> None:
    registry = {"doc-1": _chunk("doc-1", "docs/ops-runbook.md")}
    text = "Restart the cache first [[evidence:doc-1]]."
    assert replace_evidence_markers_with_path_citations(text, registry) == (
        "Restart the cache first [docs/ops-runbook.md]."
    )


def test_ensure_answer_appends_sources_when_writer_drops_markers() -> None:
    registry = {"doc-1": _chunk("doc-1", "docs/ops-runbook.md")}
    result = ensure_answer_preserves_citations(
        final_answer="Restart the cache before reindexing.",
        draft="Restart the cache before reindexing [[evidence:doc-1]].",
        registry=registry,
        evidence_ids=["doc-1"],
        require_markers=True,
    )
    assert "Restart the cache before reindexing." in result
    assert "[docs/ops-runbook.md]" in result


def test_ensure_answer_keeps_writer_path_citations() -> None:
    registry = {"doc-1": _chunk("doc-1", "docs/ops-runbook.md")}
    result = ensure_answer_preserves_citations(
        final_answer="According to [docs/ops-runbook.md], restart the cache.",
        draft="Restart [[evidence:doc-1]].",
        registry=registry,
        evidence_ids=["doc-1"],
        require_markers=True,
    )
    assert result == "According to [docs/ops-runbook.md], restart the cache."


def test_rag_citation_rule_is_defined() -> None:
    assert "path" in RAG_CITATION_RULE.lower()


def test_evidence_label_prefers_document_path_for_local_sources() -> None:
    chunk = _chunk("doc-1", "docs/ops-runbook.md")
    assert evidence_label(chunk) == "docs/ops-runbook.md"


def test_evidence_label_prefers_title_for_web_sources() -> None:
    chunk = RetrievedChunk(
        id="web-1",
        score=0.5,
        text="excerpt",
        metadata={
            "title": "Kubernetes rollout guide",
            "name": "Kubernetes rollout guide",
            "path": "https://example.com/some/long/article/path?utm=1",
            "source": "web",
        },
    )
    assert evidence_label(chunk) == "Kubernetes rollout guide"


def test_evidence_label_falls_back_to_bare_domain_for_untitled_web_sources() -> None:
    chunk = RetrievedChunk(
        id="web-2",
        score=0.5,
        text="excerpt",
        metadata={"title": "", "name": "", "path": "https://example.com/some/long/path", "source": "web"},
    )
    assert evidence_label(chunk) == "example.com"


class _WriterDropsCitationsGateway(LLMGatewayStubMixin):
    async def generate(self, *, messages, model: str, options, provider=None):
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        if "You are the synthesizer." in system_text:
            return "Restart the cache first [[evidence:doc-1]]."
        if "You are the reviewer." in system_text:
            return "Looks good."
        if "You are the writer." in system_text:
            return "Restart the cache first."
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
                    "text": "Restart the cache before reindexing.",
                    "path": "docs/ops-runbook.md",
                    "name": "ops-runbook.md",
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


def test_orchestrated_writer_appends_citations_when_dropped() -> None:
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=_WriterDropsCitationsGateway(),
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )
    response = asyncio.run(
        service.run_mode(
            mode="rag",
            query="How do I restart?",
            system_prompt="You are helpful.",
            chat_history=[],
            conversation_id=None,
            user_id="user-1",
            top_k=4,
            score_threshold=None,
            options={},
            use_rag=True,
            include_trace=False,
            persist_memory=False,
            max_steps=6,
        )
    )
    assert "Restart the cache first." in response.message
    assert "ops-runbook.md" in response.message
