"""Sparse/keyword helpers for hybrid dense+lexical retrieval."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "was",
        "one",
        "our",
        "out",
        "get",
        "has",
        "him",
        "his",
        "how",
        "its",
        "may",
        "new",
        "now",
        "old",
        "see",
        "two",
        "way",
        "who",
        "did",
        "she",
        "use",
        "what",
        "when",
        "with",
        "this",
        "that",
        "from",
        "have",
        "your",
        "about",
        "into",
        "than",
        "them",
        "then",
        "there",
        "their",
        "would",
        "which",
        "while",
        "where",
        "these",
        "those",
        "being",
        "could",
        "should",
    }
)


def tokenize_for_sparse(text: str) -> List[str]:
    tokens = [match.group(0).lower() for match in _TOKEN_RE.finditer(text or "")]
    return [token for token in tokens if token not in _STOPWORDS]


def significant_query_terms(query: str, *, max_terms: int = 6) -> List[str]:
    """Prefer rarer/longer tokens for keyword recall."""
    counts = Counter(tokenize_for_sparse(query))
    ranked = sorted(counts.keys(), key=lambda term: (-len(term), term))
    return ranked[:max_terms]


def _lexical_overlap(query: str, text: str) -> float:
    query_tokens = set(tokenize_for_sparse(query))
    if not query_tokens:
        return 0.0
    doc_tokens = set(tokenize_for_sparse(text))
    if not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def text_to_sparse_indices(text: str, *, dim: int = 30_001) -> Tuple[List[int], List[float]]:
    """
    Hashing-trick sparse bag-of-words for optional Qdrant sparse vectors.

    Indices are stable across process restarts for the same token vocabulary hashing.
    """
    counts = Counter(tokenize_for_sparse(text))
    if not counts:
        return [], []
    total = float(sum(counts.values()))
    index_to_value: Dict[int, float] = {}
    for token, count in counts.items():
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dim
        index_to_value[index] = index_to_value.get(index, 0.0) + (count / total)
    indices = sorted(index_to_value.keys())
    values = [index_to_value[index] for index in indices]
    return indices, values


def merge_dense_and_keyword_hits(
    *,
    query: str,
    dense_hits: Sequence[object],
    keyword_hits: Sequence[object],
    keyword_score_floor: float = 0.35,
) -> List[object]:
    """
    Union dense and keyword hits by id. Keyword-only hits get a synthetic score
    from lexical overlap so they survive into the rerank stage.
    """
    merged: Dict[str, object] = {}
    for hit in dense_hits:
        merged[str(getattr(hit, "id", ""))] = hit

    for hit in keyword_hits:
        hit_id = str(getattr(hit, "id", ""))
        if not hit_id or hit_id in merged:
            continue
        payload = getattr(hit, "payload", None) or {}
        text = str(payload.get("text") or "")
        lexical = _lexical_overlap(query, text)
        score = max(keyword_score_floor, lexical)
        # Preserve qdrant-like interface expected by document_retrieval merge.
        merged[hit_id] = _ScoredHit(id=hit_id, score=score, payload=payload)

    return list(merged.values())


class _ScoredHit:
    __slots__ = ("id", "score", "payload")

    def __init__(self, *, id: str, score: float, payload: dict) -> None:
        self.id = id
        self.score = score
        self.payload = payload


__all__ = [
    "merge_dense_and_keyword_hits",
    "significant_query_terms",
    "text_to_sparse_indices",
    "tokenize_for_sparse",
]
