"""Compression eval gate: ratio vs recall on the retrieval golden fixture."""

from __future__ import annotations

from pathlib import Path

from app.services.compression_eval import evaluate_compression, load_compression_cases

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval_golden.json"


def test_current_compressor_passes_compression_gate() -> None:
    cases = load_compression_cases(FIXTURES)
    result = evaluate_compression(cases, target_ratio=0.5)
    assert result["n_cases"] >= 1
    assert result["passed"], (
        f"compression gate failed: mean_recall={result['mean_recall']:.3f} "
        f"baseline={result['baseline_recall']:.3f} drop={result['recall_drop']:.3f} "
        f"ratio={result['mean_ratio']:.3f}"
    )
    assert result["mean_recall"] >= 0.70
    assert result["recall_drop"] <= 0.15


def test_regressive_prefix_compressor_fails_compression_gate() -> None:
    cases = load_compression_cases(FIXTURES)

    def keep_first_20(query: str, text: str, *, target_ratio: float = 0.5) -> str:
        del query, target_ratio
        return (text or "")[:20]

    result = evaluate_compression(cases, target_ratio=0.5, compressor=keep_first_20)
    assert result["passed"] is False
    assert result["mean_recall"] < 0.70 or result["recall_drop"] > 0.15
    assert result["mean_recall"] < result["baseline_recall"]
