"""Retrieve-wide, pack-narrow: hybrid rerank + MMR diversity selection."""

from __future__ import annotations

import re
from typing import List, Sequence, Set

from app.services.document_summary import DOCUMENT_SUMMARY_CHUNK_TYPE

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
        "her",
        "was",
        "one",
        "our",
        "out",
        "day",
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
        "boy",
        "did",
        "she",
        "use",
        "her",
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


def _tokenize(text: str) -> Set[str]:
    tokens = {match.group(0).lower() for match in _TOKEN_RE.finditer(text or "")}
    return {token for token in tokens if token not in _STOPWORDS}


def lexical_overlap_score(query: str, text: str) -> float:
    """Normalized query-term overlap in candidate text (0.0–1.0)."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    doc_tokens = _tokenize(text)
    if not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def _normalize_scores(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if maximum <= minimum:
        return [1.0 for _ in values]
    span = maximum - minimum
    return [(value - minimum) / span for value in values]


def hybrid_rerank_score(
    *,
    query: str,
    chunk: RetrievedChunk,
    normalized_vector_score: float,
    vector_weight: float = 0.45,
    lexical_weight: float = 0.55,
    prefer_document_summaries: bool = False,
    summary_boost: float = 0.12,
) -> float:
    lexical = lexical_overlap_score(query, chunk.text)
    score = (vector_weight * normalized_vector_score) + (lexical_weight * lexical)
    if prefer_document_summaries and (chunk.metadata or {}).get("chunk_type") == DOCUMENT_SUMMARY_CHUNK_TYPE:
        score += summary_boost
    return score


NEAR_DUPLICATE_JACCARD = 0.75


def rerank_and_pack(
    query: str,
    candidates: Sequence[RetrievedChunk],
    *,
    limit: int,
    vector_weight: float = 0.45,
    lexical_weight: float = 0.55,
    diversity_lambda: float = 0.55,
    prefer_document_summaries: bool = False,
    summary_boost: float = 0.12,
) -> List[RetrievedChunk]:
    """
    Rerank vector hits with hybrid scores, then pack with MMR for diversity.

    Returns at most `limit` chunks. Original vector scores are preserved on each chunk.
    """
    if limit <= 0 or not candidates:
        return []
    if len(candidates) <= limit and not prefer_document_summaries:
        return list(candidates)

    summary_candidates = [
        candidate
        for candidate in candidates
        if (candidate.metadata or {}).get("chunk_type") == DOCUMENT_SUMMARY_CHUNK_TYPE
    ]
    chunk_candidates = [
        candidate
        for candidate in candidates
        if (candidate.metadata or {}).get("chunk_type") != DOCUMENT_SUMMARY_CHUNK_TYPE
    ]

    if prefer_document_summaries and summary_candidates and chunk_candidates:
        summary_slots = min(len(summary_candidates), max(1, limit // 2))
        summary_packed = _rerank_candidates(
            query,
            summary_candidates,
            limit=summary_slots,
            vector_weight=vector_weight,
            lexical_weight=lexical_weight,
            diversity_lambda=diversity_lambda,
            prefer_document_summaries=True,
            summary_boost=summary_boost,
        )
        remaining = limit - len(summary_packed)
        chunk_packed = (
            _rerank_candidates(
                query,
                chunk_candidates,
                limit=remaining,
                vector_weight=vector_weight,
                lexical_weight=lexical_weight,
                diversity_lambda=diversity_lambda,
                prefer_document_summaries=False,
                summary_boost=summary_boost,
            )
            if remaining > 0
            else []
        )
        return summary_packed + chunk_packed

    return _rerank_candidates(
        query,
        candidates,
        limit=limit,
        vector_weight=vector_weight,
        lexical_weight=lexical_weight,
        diversity_lambda=diversity_lambda,
        prefer_document_summaries=prefer_document_summaries,
        summary_boost=summary_boost,
    )


def _rerank_candidates(
    query: str,
    candidates: Sequence[RetrievedChunk],
    *,
    limit: int,
    vector_weight: float,
    lexical_weight: float,
    diversity_lambda: float,
    prefer_document_summaries: bool,
    summary_boost: float,
) -> List[RetrievedChunk]:
    if limit <= 0 or not candidates:
        return []
    if len(candidates) <= limit:
        return list(candidates)

    normalized_vectors = _normalize_scores([candidate.score for candidate in candidates])
    scored = [
        (
            hybrid_rerank_score(
                query=query,
                chunk=candidate,
                normalized_vector_score=normalized_vectors[index],
                vector_weight=vector_weight,
                lexical_weight=lexical_weight,
                prefer_document_summaries=prefer_document_summaries,
                summary_boost=summary_boost,
            ),
            candidate,
        )
        for index, candidate in enumerate(candidates)
    ]
    scored.sort(key=lambda item: item[0], reverse=True)

    selected: List[RetrievedChunk] = []

    while scored and len(selected) < limit:
        best_index: int | None = None
        best_mmr = float("-inf")
        fallback_index: int | None = None
        fallback_relevance = float("-inf")

        for index, (relevance, candidate) in enumerate(scored):
            if fallback_relevance < relevance:
                fallback_relevance = relevance
                fallback_index = index

            if not selected:
                mmr = relevance
            else:
                max_similarity = max(_jaccard_similarity(candidate.text, picked.text) for picked in selected)
                if max_similarity >= NEAR_DUPLICATE_JACCARD:
                    continue
                penalty = max_similarity * max_similarity
                mmr = (diversity_lambda * relevance) - ((1.0 - diversity_lambda) * penalty)
            if mmr > best_mmr:
                best_mmr = mmr
                best_index = index

        if best_index is None:
            if fallback_index is None:
                break
            best_index = fallback_index

        _relevance, chosen = scored.pop(best_index)
        selected.append(chosen)

    return selected


def wide_retrieval_limit(*, pack_limit: int, wide_top_k: int, rerank_enabled: bool) -> int:
    """How many vector hits to fetch before reranking."""
    if not rerank_enabled:
        return pack_limit
    return max(pack_limit, wide_top_k)


__all__ = [
    "hybrid_rerank_score",
    "lexical_overlap_score",
    "rerank_and_pack",
    "wide_retrieval_limit",
]
