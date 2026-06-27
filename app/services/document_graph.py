"""Lightweight entity/topic signals for GraphRAG-style cross-document linking."""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Set

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,}", re.IGNORECASE)
_ENTITY_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
_TOPIC_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "your",
        "about",
        "into",
        "document",
        "summary",
        "section",
        "chapter",
        "page",
        "note",
        "notes",
        "file",
        "files",
    }
)


def _tokenize(text: str) -> List[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text or "")]


def _lexical_overlap(query: str, text: str) -> float:
    query_tokens = {token for token in _tokenize(query) if token not in _TOPIC_STOPWORDS}
    if not query_tokens:
        return 0.0
    doc_tokens = {token for token in _tokenize(text) if token not in _TOPIC_STOPWORDS}
    if not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def extract_document_graph_signals(text: str, *, max_entities: int = 12, max_topics: int = 8) -> Dict[str, List[str]]:
    """Extract compact entity/topic signals stored on summary index points."""
    cleaned = (text or "").strip()
    if not cleaned:
        return {"graph_entities": [], "graph_topics": []}

    entities: List[str] = []
    seen_entities: Set[str] = set()
    for match in _ENTITY_RE.finditer(cleaned):
        value = " ".join(match.group(0).split())
        key = value.lower()
        if len(value) < 3 or key in seen_entities:
            continue
        seen_entities.add(key)
        entities.append(value)
        if len(entities) >= max_entities:
            break

    topic_counts: Dict[str, int] = {}
    for token in _tokenize(cleaned):
        if len(token) < 4 or token in _TOPIC_STOPWORDS:
            continue
        topic_counts[token] = topic_counts.get(token, 0) + 1

    topics = [
        token
        for token, _count in sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))
        if token not in {entity.lower() for entity in entities}
    ][:max_topics]

    return {"graph_entities": entities, "graph_topics": topics}


def extract_query_graph_signals(query: str) -> Dict[str, Set[str]]:
    document_signals = extract_document_graph_signals(query, max_entities=10, max_topics=10)
    entities = {value.lower() for value in document_signals["graph_entities"]}
    topics = {value.lower() for value in document_signals["graph_topics"]}
    for token in _tokenize(query):
        if len(token) >= 4 and token not in _TOPIC_STOPWORDS:
            topics.add(token)
    return {"entities": entities, "topics": topics}


def graph_overlap_score(query_signals: Dict[str, Set[str]], metadata: Dict[str, object]) -> float:
    """Score overlap between query signals and stored graph metadata."""
    stored_entities = {
        str(value).lower()
        for value in (metadata.get("graph_entities") or [])
        if str(value).strip()
    }
    stored_topics = {
        str(value).lower()
        for value in (metadata.get("graph_topics") or [])
        if str(value).strip()
    }
    if not stored_entities and not stored_topics:
        return 0.0

    entity_overlap = len(query_signals["entities"] & stored_entities)
    topic_overlap = len(query_signals["topics"] & stored_topics)
    query_size = max(1, len(query_signals["entities"] | query_signals["topics"]))
    return min(1.0, (entity_overlap * 1.0 + topic_overlap * 0.6) / query_size)


def shared_graph_neighbors(
    selected_document_ids: Sequence[str],
    summaries_by_document: Dict[str, object],
) -> Set[str]:
    """Return document IDs that share graph entities with already-selected docs."""
    selected_entities: Set[str] = set()
    for document_id in selected_document_ids:
        metadata = getattr(summaries_by_document.get(document_id), "metadata", None) or {}
        if isinstance(metadata, dict):
            selected_entities.update(str(value).lower() for value in metadata.get("graph_entities") or [])

    neighbors: Set[str] = set()
    if not selected_entities:
        return neighbors

    for document_id, summary in summaries_by_document.items():
        if document_id in selected_document_ids:
            continue
        metadata = summary.metadata or {}
        entities = {str(value).lower() for value in metadata.get("graph_entities") or []}
        if entities & selected_entities:
            neighbors.add(document_id)
    return neighbors


def hybrid_corpus_score(query: str, chunk, *, query_signals: Dict[str, Set[str]], graph_boost: float) -> float:
    payload = chunk.metadata or {}
    vector_score = float(chunk.score)
    lexical = _lexical_overlap(query, chunk.text)
    graph = graph_overlap_score(query_signals, payload)
    return (0.45 * vector_score) + (0.40 * lexical) + (graph_boost * graph)


__all__ = [
    "extract_document_graph_signals",
    "extract_query_graph_signals",
    "graph_overlap_score",
    "hybrid_corpus_score",
    "shared_graph_neighbors",
]
