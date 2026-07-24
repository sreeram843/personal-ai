"""Retrieval quality metrics: recall@k and MRR."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Set


def _normalize_label(value: str) -> str:
    return (value or "").strip().lower()


def ranked_labels(paths_or_ids: Sequence[str]) -> List[str]:
    return [_normalize_label(item) for item in paths_or_ids if _normalize_label(item)]


def relevant_set(expected: Iterable[str]) -> Set[str]:
    return {_normalize_label(item) for item in expected if _normalize_label(item)}


def recall_at_k(ranked: Sequence[str], expected: Iterable[str], *, k: int) -> float:
    """Fraction of relevant labels recovered in the top-k ranked results."""
    truth = relevant_set(expected)
    if not truth or k <= 0:
        return 0.0
    top = set(ranked_labels(ranked)[:k])
    return len(truth & top) / len(truth)


def mean_reciprocal_rank(ranked: Sequence[str], expected: Iterable[str]) -> float:
    """
    MRR for a single query: 1/rank of the first relevant hit (0 if none).

    For multi-relevant queries this uses the first relevant label in the ranking.
    """
    truth = relevant_set(expected)
    if not truth:
        return 0.0
    for index, label in enumerate(ranked_labels(ranked), start=1):
        if label in truth:
            return 1.0 / index
    return 0.0


def average_metric(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


__all__ = [
    "average_metric",
    "mean_reciprocal_rank",
    "recall_at_k",
    "relevant_set",
    "ranked_labels",
]
