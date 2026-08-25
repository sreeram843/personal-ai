"""Golden grounding-gate eval plus writer retry/reject behavior."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.schemas.chat import RetrievedChunk
from app.services.grounding_gate import (
    enforce_grounding_gate,
    extract_evidence_markers,
    ungrounded_claim_spans,
)
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.orchestrated_chat import OrchestratedChatService
from tests.llm_gateway_stub import LLMGatewayStubMixin

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "grounding_gate.json"
GOLDEN_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]

_UNVERIFIED_FALLBACK = (
    "I cannot verify key claims from the available evidence. "
    "Please review the cited sources or broaden retrieval before finalizing."
)


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case["id"])
def test_grounding_gate_golden_fixture(case: dict) -> None:
    ok, reason = enforce_grounding_gate(
        writer_text=case["text"],
        evidence_ids=case["evidence_ids"],
        registry_paths=case.get("registry_paths") or [],
    )
    if case["expect_pass"]:
        assert ok, f"{case['id']} should pass, got: {reason}"
        assert reason == ""
    else:
        assert not ok, f"{case['id']} must be rejected, but the gate passed"
        assert "Ungrounded" in reason
        gaps = ungrounded_claim_spans(
            case["text"],
            case["evidence_ids"],
            registry_paths=case.get("registry_paths") or [],
        )
        assert gaps, f"{case['id']} must surface at least one ungrounded span"


def test_extract_evidence_markers_preserves_order() -> None:
    text = "First [[evidence:doc-1]] then [[evidence:web-2]] and [[evidence:doc-1]]."
    assert extract_evidence_markers(text) == ["doc-1", "web-2", "doc-1"]


class _RejectingWriterGateway(LLMGatewayStubMixin):
    def __init__(self) -> None:
        self.writer_calls = 0
        self.retry_saw_ungrounded_note = False

    async def generate(self, *, messages, model: str, options, provider=None):
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        if "You are the writer." in system_text:
            self.writer_calls += 1
            if "Ungrounded claims" in system_text:
                self.retry_saw_ungrounded_note = True
            return "Acme Corp posted $9 million last quarter without citing anything."
        return "ok"


class _FixesOnRetryGateway(LLMGatewayStubMixin):
    def __init__(self) -> None:
        self.writer_calls = 0

    async def generate(self, *, messages, model: str, options, provider=None):
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        if "You are the writer." in system_text:
            self.writer_calls += 1
            if self.writer_calls == 1:
                return "Acme Corp posted $9 million last quarter."
            return "Acme Corp posted $9 million last quarter [[evidence:doc-1]]."
        return "ok"


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _StubVectorStore:
    def search(self, vector, *, user_id: str, limit=4, score_threshold=None, query_text=None, hybrid=False):
        return []


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


def _writer_state() -> dict:
    return {
        "query": "What was revenue?",
        "system_prompt": "You are helpful.",
        "chat_history": [],
        "draft": "Acme Corp posted $9 million last quarter [[evidence:doc-1]].",
        "review_notes": "Looks good.",
        "memory_summary": "",
        "retrieval_context": "",
        "web_context": "",
        "evidence_ids": ["doc-1"],
        "evidence_registry": {
            "doc-1": RetrievedChunk(
                id="doc-1",
                score=0.9,
                text="Internal note about cache restarts.",
                metadata={"path": "docs/ops-runbook.md", "name": "ops-runbook.md"},
            )
        },
        "require_evidence_markers": True,
        "progressive_disclosure_level": "compact",
    }


def _make_service(gateway: LLMGatewayStubMixin) -> OrchestratedChatService:
    return OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=gateway,
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )


def test_run_writer_retries_then_rejects_ungrounded_claims() -> None:
    gateway = _RejectingWriterGateway()
    service = _make_service(gateway)
    state = _writer_state()
    outcome = asyncio.run(service._run_writer(state, {}))
    assert gateway.writer_calls == 2
    assert gateway.retry_saw_ungrounded_note
    assert outcome.output == _UNVERIFIED_FALLBACK
    assert state["final_answer"] == _UNVERIFIED_FALLBACK
    assert "$9 million" not in outcome.output


def test_run_writer_accepts_grounded_retry() -> None:
    gateway = _FixesOnRetryGateway()
    service = _make_service(gateway)
    state = _writer_state()
    outcome = asyncio.run(service._run_writer(state, {}))
    assert gateway.writer_calls == 2
    assert outcome.output != _UNVERIFIED_FALLBACK
    assert "cannot verify" not in outcome.output.lower()
    assert "ops-runbook.md" in outcome.output or "[[evidence:doc-1]]" in outcome.output
