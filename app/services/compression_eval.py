"""Offline eval for extractive context compression vs retrieval recall.

Strategy: compress each candidate independently (not as one concatenated corpus).
Rerank/pack then uses the compressed texts, so a compressor that throws away
query-distinctive tokens will drop recall even if the ratio looks better.

Golden fixture chunks are often shorter than the production min-char skip
(`compress_text_for_query` defaults to 400). The default compressor therefore
passes ``min_chars_to_compress=0`` so the extractive path actually runs.
Pack limit and recall@k follow each case's ``top_k``: a global k=5 would skip
rerank because every current golden case has fewer than 5 candidates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from app.schemas.chat import RetrievedChunk
from app.services.context_compression import compress_text_for_query
from app.services.retrieval_metrics import average_metric, recall_at_k
from app.services.retrieval_rerank import rerank_and_pack

DEFAULT_GOLDEN_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "retrieval_golden.json"
)
DEFAULT_TARGET_RATIO = 0.5
MAX_RECALL_DROP = 0.15
MIN_MEAN_RECALL = 0.70

CompressorFn = Callable[..., str]


def load_compression_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load golden cases that include candidate chunks with text."""
    golden_path = Path(path) if path is not None else DEFAULT_GOLDEN_PATH
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    return [case for case in payload if _has_candidate_text(case)]


def _has_candidate_text(case: Mapping[str, Any]) -> bool:
    candidates = case.get("candidates") or []
    return any(str(chunk.get("text") or "").strip() for chunk in candidates)


def _default_compressor(query: str, text: str, *, target_ratio: float) -> str:
    return compress_text_for_query(
        query,
        text,
        target_ratio=target_ratio,
        min_chars_to_compress=0,
    )


def _chunks_from_case(
    case: Mapping[str, Any],
    *,
    texts: Optional[Sequence[str]] = None,
) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    for index, chunk in enumerate(case["candidates"]):
        text = texts[index] if texts is not None else str(chunk.get("text") or "")
        chunks.append(
            RetrievedChunk(
                id=str(chunk["id"]),
                score=float(chunk["score"]),
                text=text,
                metadata=dict(chunk.get("metadata") or {}),
            )
        )
    return chunks


def _packed_paths(query: str, chunks: Sequence[RetrievedChunk], *, limit: int) -> list[str]:
    packed = rerank_and_pack(query, chunks, limit=limit)
    return [str((chunk.metadata or {}).get("path") or "") for chunk in packed]


def _case_recall(
    case: Mapping[str, Any],
    *,
    texts: Optional[Sequence[str]] = None,
) -> float:
    query = str(case["query"])
    limit = int(case.get("top_k") or 5)
    ranked = _packed_paths(query, _chunks_from_case(case, texts=texts), limit=limit)
    return recall_at_k(ranked, case.get("expected_paths") or [], k=limit)


def evaluate_compression(
    cases: Sequence[Mapping[str, Any]],
    *,
    target_ratio: float = DEFAULT_TARGET_RATIO,
    compressor: Optional[CompressorFn] = None,
    max_recall_drop: float = MAX_RECALL_DROP,
    min_mean_recall: float = MIN_MEAN_RECALL,
) -> dict[str, Any]:
    """Score a compressor on golden retrieval cases.

    Returns mean_recall (compressed), mean_ratio (compressed_len / original_len),
    baseline_recall (uncompressed rerank), and ``passed`` for the recall gate.
    """
    compress = compressor or _default_compressor
    eligible = [case for case in cases if _has_candidate_text(case)]

    compressed_recalls: list[float] = []
    baseline_recalls: list[float] = []
    ratios: list[float] = []

    for case in eligible:
        original_texts = [str(chunk.get("text") or "") for chunk in case["candidates"]]
        compressed_texts = [
            str(compress(str(case["query"]), text, target_ratio=target_ratio) or "")
            for text in original_texts
        ]
        original_len = sum(len(text) for text in original_texts)
        compressed_len = sum(len(text) for text in compressed_texts)
        if original_len > 0:
            ratios.append(compressed_len / original_len)

        compressed_recalls.append(_case_recall(case, texts=compressed_texts))
        baseline_recalls.append(_case_recall(case, texts=original_texts))

    mean_recall = average_metric(compressed_recalls)
    baseline_recall = average_metric(baseline_recalls)
    mean_ratio = average_metric(ratios)
    recall_drop = baseline_recall - mean_recall
    passed = mean_recall >= min_mean_recall and recall_drop <= max_recall_drop

    return {
        "mean_recall": mean_recall,
        "mean_ratio": mean_ratio,
        "baseline_recall": baseline_recall,
        "recall_drop": recall_drop,
        "passed": passed,
        "n_cases": len(eligible),
        "max_recall_drop": max_recall_drop,
        "min_mean_recall": min_mean_recall,
        "target_ratio": target_ratio,
    }


__all__ = [
    "DEFAULT_GOLDEN_PATH",
    "DEFAULT_TARGET_RATIO",
    "MAX_RECALL_DROP",
    "MIN_MEAN_RECALL",
    "evaluate_compression",
    "load_compression_cases",
]
