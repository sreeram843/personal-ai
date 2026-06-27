"""Per-document summary index for corpus-level retrieval."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence

from app.core.config import Settings
from app.schemas.documents import IngestDocument
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.document_graph import extract_document_graph_signals
from app.services.sentence_window import split_sentences
from app.services.vector_store import StoredDocument

logger = logging.getLogger(__name__)

DOCUMENT_SUMMARY_CHUNK_TYPE = "document_summary"
_SUMMARY_SYSTEM = (
    "Summarize the document for semantic search retrieval. "
    "Include main topics, key entities, and conclusions. "
    "Plain text only — no markdown headings or bullet lists."
)


def resolve_ingest_document_id(document: IngestDocument) -> str:
    """Stable identifier for summary points and chunk grouping."""
    if document.id:
        return str(document.id).strip()
    metadata = document.metadata or {}
    for key in ("path", "title", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    digest = hashlib.sha256(document.text.encode("utf-8")).hexdigest()
    return digest[:16]


def summary_point_id(document_id: str) -> str:
    """Deterministic Qdrant point id for a document summary."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"document-summary:{document_id}"))


def build_heuristic_document_summary(text: str, *, max_chars: int) -> str:
    """Extractive fallback summary without an LLM call."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    sentences = split_sentences(cleaned)
    if not sentences:
        sentences = [cleaned]

    parts: List[str] = []
    total = 0
    for sentence in sentences:
        next_len = len(sentence) + (2 if parts else 0)
        if parts and total + next_len > max_chars:
            break
        parts.append(sentence)
        total += next_len
        if total >= max_chars:
            break

    summary = " ".join(parts).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


async def generate_document_summary(
    text: str,
    *,
    settings: Settings,
    llm_gateway: Optional[LLMGateway] = None,
    model_profile: Optional[WorkflowModelProfile] = None,
) -> tuple[str, str]:
    """Return (summary_text, summary_source) where source is 'llm' or 'heuristic'."""
    cleaned = (text or "").strip()
    if not cleaned:
        return "", "heuristic"

    max_chars = settings.document_summary_max_chars
    max_input = settings.document_summary_max_input_chars
    input_text = cleaned if len(cleaned) <= max_input else cleaned[:max_input].rstrip() + "..."

    if llm_gateway is not None and model_profile is not None:
        try:
            response = await llm_gateway.generate(
                messages=[
                    {
                        "role": "system",
                        "content": f"{_SUMMARY_SYSTEM}\nKeep the summary under {max_chars} characters.",
                    },
                    {"role": "user", "content": input_text},
                ],
                model=settings.document_summary_model,
                provider=settings.document_summary_provider,
                options={"temperature": 0.2},
            )
            summary = " ".join(str(response or "").split()).strip()
            if summary:
                if len(summary) > max_chars:
                    summary = summary[: max_chars - 3].rstrip() + "..."
                return summary, "llm"
        except Exception:
            logger.info("LLM document summary failed; using heuristic fallback", exc_info=True)

    return build_heuristic_document_summary(cleaned, max_chars=max_chars), "heuristic"


def _document_label(metadata: Dict[str, Any]) -> str:
    for key in ("path", "title", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "document"


def build_summary_stored_document(
    *,
    document_id: str,
    summary: str,
    metadata: Dict[str, Any],
    user_id: str,
    summary_source: str,
) -> StoredDocument:
    label = _document_label(metadata)
    text = f"Document summary ({label}): {summary}".strip()
    graph_signals = extract_document_graph_signals(f"{summary}\n{metadata.get('path', '')}")
    return StoredDocument(
        id=summary_point_id(document_id),
        text=text,
        metadata={
            **metadata,
            "document_id": document_id,
            "chunk_type": DOCUMENT_SUMMARY_CHUNK_TYPE,
            "summary_source": summary_source,
            "user_id": user_id,
            **graph_signals,
        },
    )


async def build_document_summary_points(
    documents: Sequence[IngestDocument],
    *,
    settings: Settings,
    user_id: str,
    llm_gateway: Optional[LLMGateway] = None,
    model_profile: Optional[WorkflowModelProfile] = None,
) -> List[StoredDocument]:
    """Build one embedded summary point per uploaded document."""
    if not settings.enable_document_summary_index:
        return []

    points: List[StoredDocument] = []
    for document in documents:
        document_id = resolve_ingest_document_id(document)
        summary, summary_source = await generate_document_summary(
            document.text,
            settings=settings,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
        )
        if not summary:
            continue
        metadata = dict(document.metadata or {})
        metadata.setdefault("document_id", document_id)
        points.append(
            build_summary_stored_document(
                document_id=document_id,
                summary=summary,
                metadata=metadata,
                user_id=user_id,
                summary_source=summary_source,
            )
        )
    return points


__all__ = [
    "DOCUMENT_SUMMARY_CHUNK_TYPE",
    "build_document_summary_points",
    "build_heuristic_document_summary",
    "build_summary_stored_document",
    "generate_document_summary",
    "resolve_ingest_document_id",
    "summary_point_id",
]
