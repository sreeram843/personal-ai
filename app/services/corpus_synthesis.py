"""RAPTOR/GraphRAG-lite retrieval for cross-document synthesis queries."""

from __future__ import annotations

from typing import Dict, List, Sequence

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk
from app.services.document_graph import (
    extract_query_graph_signals,
    hybrid_corpus_score,
    shared_graph_neighbors,
)
from app.services.document_summary import DOCUMENT_SUMMARY_CHUNK_TYPE
from app.services.information_routing import is_corpus_overview_query
from app.services.retrieval_rerank import rerank_and_pack


def should_use_corpus_synthesis(query: str, *, settings: Settings) -> bool:
    return settings.enable_corpus_synthesis and is_corpus_overview_query(query)


def _document_id(chunk: RetrievedChunk) -> str:
    metadata = chunk.metadata or {}
    document_id = metadata.get("document_id")
    if isinstance(document_id, str) and document_id.strip():
        return document_id.strip()
    for key in ("path", "title", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return chunk.id


def _is_summary_chunk(chunk: RetrievedChunk) -> bool:
    return (chunk.metadata or {}).get("chunk_type") == DOCUMENT_SUMMARY_CHUNK_TYPE


def pack_corpus_synthesis(
    query: str,
    candidates: Sequence[RetrievedChunk],
    *,
    settings: Settings,
    pack_limit: int,
) -> List[RetrievedChunk]:
    """
    RAPTOR-style pack: one summary per document, graph-linked expansion, optional detail chunk.
    """
    if not candidates:
        return []

    query_signals = extract_query_graph_signals(query)
    summaries = [chunk for chunk in candidates if _is_summary_chunk(chunk)]
    detail_chunks = [chunk for chunk in candidates if not _is_summary_chunk(chunk)]

    if not summaries:
        return rerank_and_pack(
            query,
            candidates,
            limit=min(pack_limit, len(candidates)),
            prefer_document_summaries=True,
            summary_boost=settings.retrieval_summary_boost,
        )

    ranked_summaries = sorted(
        summaries,
        key=lambda chunk: hybrid_corpus_score(
            query,
            chunk,
            query_signals=query_signals,
            graph_boost=settings.corpus_synthesis_graph_boost,
        ),
        reverse=True,
    )

    summaries_by_document: Dict[str, RetrievedChunk] = {}
    for summary in ranked_summaries:
        document_id = _document_id(summary)
        if document_id not in summaries_by_document:
            summaries_by_document[document_id] = summary

    max_documents = max(1, settings.corpus_synthesis_max_documents)
    selected_ids: List[str] = []
    selected: List[RetrievedChunk] = []

    for summary in ranked_summaries:
        document_id = _document_id(summary)
        if document_id in selected_ids:
            continue
        selected_ids.append(document_id)
        selected.append(summary)
        if len(selected_ids) >= max_documents:
            break

    neighbor_ids = shared_graph_neighbors(selected_ids, summaries_by_document)
    for summary in ranked_summaries:
        if len(selected) >= pack_limit:
            break
        document_id = _document_id(summary)
        if document_id in selected_ids or document_id not in neighbor_ids:
            continue
        selected_ids.append(document_id)
        selected.append(summary)

    if settings.corpus_synthesis_include_supporting_chunks and detail_chunks:
        chunks_by_document: Dict[str, List[RetrievedChunk]] = {}
        for chunk in detail_chunks:
            chunks_by_document.setdefault(_document_id(chunk), []).append(chunk)

        for document_id in selected_ids:
            doc_chunks = chunks_by_document.get(document_id) or []
            if not doc_chunks:
                continue
            best_chunk = max(
                doc_chunks,
                key=lambda chunk: hybrid_corpus_score(
                    query,
                    chunk,
                    query_signals=query_signals,
                    graph_boost=settings.corpus_synthesis_graph_boost,
                ),
            )
            if best_chunk.id in {item.id for item in selected}:
                continue
            selected.append(best_chunk)

    return selected[:pack_limit]


__all__ = ["pack_corpus_synthesis", "should_use_corpus_synthesis"]
