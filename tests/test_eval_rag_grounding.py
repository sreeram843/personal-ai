"""RAG grounding and response quality guard tests."""

from __future__ import annotations

from app.api.routes import _format_chat_response
from app.schemas.chat import ChatResponse, RetrievedChunk


def test_format_chat_response_strips_legacy_prefixes() -> None:
    assert _format_chat_response("MACHINE_ALPHA_7: > Final answer") == "Final answer"
    assert _format_chat_response("> quoted") == "quoted"
    assert _format_chat_response("") == "I couldn't generate a response. Please try again."


def test_rag_response_preserves_source_metadata_for_citation_accuracy() -> None:
    response = ChatResponse(
        message="According to [ops-runbook.md], restart the cache first.",
        sources=[
            RetrievedChunk(
                id="doc-1",
                score=0.97,
                text="Restart the cache before reindexing.",
                metadata={"name": "ops-runbook.md", "path": "docs/runbooks/ops-runbook.md"},
            )
        ],
    )
    assert "ops-runbook.md" in response.message
    assert response.sources
    assert response.sources[0].metadata["path"] == "docs/runbooks/ops-runbook.md"
    assert response.sources[0].score is not None and response.sources[0].score >= 0.9
