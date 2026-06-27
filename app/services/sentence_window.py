"""Sentence-window chunking for ingest and retrieval-time context expansion."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from app.services.vector_store import StoredDocument

logger = logging.getLogger(__name__)

WINDOW_METADATA_KEY = "window"
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class SentenceWindowChunk:
    """One embeddable sentence plus surrounding context for retrieval."""

    sentence: str
    window: str
    metadata: Dict[str, Any]


def split_sentences(text: str) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    parts = SENTENCE_SPLIT_RE.split(cleaned)
    return [part.strip() for part in parts if part.strip()]


def build_sentence_window_chunks(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    window_size: int = 3,
) -> List[SentenceWindowChunk]:
    """Split text into sentence chunks with symmetric context windows."""
    base_metadata = dict(metadata or {})
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: List[SentenceWindowChunk] = []
    for index, sentence in enumerate(sentences):
        start = max(0, index - window_size)
        end = min(len(sentences), index + window_size + 1)
        window = " ".join(sentences[start:end])
        chunk_metadata = {
            **base_metadata,
            WINDOW_METADATA_KEY: window,
            "sentence_index": index,
            "chunking": "sentence_window",
        }
        chunks.append(SentenceWindowChunk(sentence=sentence, window=window, metadata=chunk_metadata))
    return chunks


def _parse_with_llamaindex(
    text: str,
    metadata: Dict[str, Any],
    *,
    window_size: int,
) -> List[SentenceWindowChunk]:
    from app.services.llamaindex_rag import parse_sentence_window_chunks_with_llamaindex

    return parse_sentence_window_chunks_with_llamaindex(text, metadata, window_size=window_size)


def parse_sentence_window_chunks(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    window_size: int = 3,
    prefer_llamaindex: bool = True,
) -> List[SentenceWindowChunk]:
    """Parse chunks with LlamaIndex when available, otherwise native splitting."""
    base_metadata = dict(metadata or {})
    if prefer_llamaindex:
        try:
            return _parse_with_llamaindex(text, base_metadata, window_size=window_size)
        except Exception as exc:
            logger.info("LlamaIndex sentence-window parser unavailable; using native fallback: %s", exc)
    return build_sentence_window_chunks(text, base_metadata, window_size=window_size)


def stored_documents_from_sentence_chunks(
    documents: Sequence[Any],
    *,
    user_id: str,
    window_size: int,
    prefer_llamaindex: bool = True,
) -> List[StoredDocument]:
    """Expand uploaded documents into StoredDocument sentence-window chunks."""
    stored: List[StoredDocument] = []
    for document in documents:
        text = str(getattr(document, "text", None) or document.get("text", ""))
        raw_metadata = getattr(document, "metadata", None)
        if raw_metadata is None and isinstance(document, dict):
            raw_metadata = document.get("metadata")
        metadata = dict(raw_metadata or {})
        document_id = getattr(document, "id", None)
        if document_id is None and isinstance(document, dict):
            document_id = document.get("id")
        if document_id:
            metadata.setdefault("document_id", document_id)

        for chunk in parse_sentence_window_chunks(
            text,
            metadata,
            window_size=window_size,
            prefer_llamaindex=prefer_llamaindex,
        ):
            stored.append(
                StoredDocument(
                    text=chunk.sentence,
                    metadata={**chunk.metadata, WINDOW_METADATA_KEY: chunk.window, "user_id": user_id},
                )
            )
    return stored


def resolve_retrieval_text(payload: Dict[str, Any]) -> str:
    """Prefer sentence-window context over the embedded sentence at retrieval time."""
    window = payload.get(WINDOW_METADATA_KEY)
    if isinstance(window, str) and window.strip():
        return window.strip()
    return str(payload.get("text", ""))


__all__ = [
    "WINDOW_METADATA_KEY",
    "SentenceWindowChunk",
    "build_sentence_window_chunks",
    "parse_sentence_window_chunks",
    "resolve_retrieval_text",
    "split_sentences",
    "stored_documents_from_sentence_chunks",
]
