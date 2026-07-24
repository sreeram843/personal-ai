"""Unit tests for recall@k and MRR helpers."""

from __future__ import annotations

from app.services.retrieval_metrics import average_metric, mean_reciprocal_rank, recall_at_k


def test_recall_at_k() -> None:
    ranked = ["a", "b", "c"]
    assert recall_at_k(ranked, ["a", "c"], k=2) == 0.5
    assert recall_at_k(ranked, ["a", "c"], k=3) == 1.0


def test_mean_reciprocal_rank() -> None:
    assert mean_reciprocal_rank(["x", "target", "y"], ["target"]) == 0.5
    assert mean_reciprocal_rank(["nope", "also-no"], ["target"]) == 0.0


def test_average_metric() -> None:
    assert average_metric([1.0, 0.5]) == 0.75
    assert average_metric([]) == 0.0
