"""Retrieval golden-set evaluation (rerank/pack + recall@k / MRR + routing hints)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.chat import RetrievedChunk
from app.services.information_routing import is_corpus_overview_query, is_document_grounded_query
from app.services.retrieval_metrics import average_metric, mean_reciprocal_rank, recall_at_k
from app.services.retrieval_rerank import rerank_and_pack

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval_golden.json"
GOLDEN_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))
RERANK_CASES = [case for case in GOLDEN_CASES if case.get("candidates")]
ROUTING_CASES = [case for case in GOLDEN_CASES if "expect_document_grounded" in case]

# Gates for the offline golden set (hybrid lexical rerank). Raise over time as the
# set grows and/or live embedding eval is wired into CI.
MIN_MEAN_RECALL_AT_K = 0.85
MIN_MEAN_MRR = 0.80


def _packed_paths(case: dict) -> list[str]:
    candidates = [
        RetrievedChunk(
            id=chunk["id"],
            score=float(chunk["score"]),
            text=chunk["text"],
            metadata=dict(chunk.get("metadata") or {}),
        )
        for chunk in case["candidates"]
    ]
    packed = rerank_and_pack(case["query"], candidates, limit=int(case["top_k"]))
    return [str((chunk.metadata or {}).get("path") or "") for chunk in packed]


@pytest.mark.parametrize("case", RERANK_CASES, ids=lambda case: case["id"])
def test_retrieval_rerank_golden_fixture(case: dict) -> None:
    packed_paths = _packed_paths(case)
    for expected_path in case["expected_paths"]:
        assert expected_path in packed_paths, (
            f"Expected {expected_path} in top-{case['top_k']}, got {packed_paths}"
        )


def test_retrieval_golden_mean_recall_and_mrr() -> None:
    recalls: list[float] = []
    mrrs: list[float] = []
    for case in RERANK_CASES:
        ranked = _packed_paths(case)
        k = int(case["top_k"])
        expected = case["expected_paths"]
        recalls.append(recall_at_k(ranked, expected, k=k))
        mrrs.append(mean_reciprocal_rank(ranked, expected))

    mean_recall = average_metric(recalls)
    mean_mrr = average_metric(mrrs)
    assert mean_recall >= MIN_MEAN_RECALL_AT_K, (
        f"mean recall@k {mean_recall:.3f} below gate {MIN_MEAN_RECALL_AT_K}"
    )
    assert mean_mrr >= MIN_MEAN_MRR, f"mean MRR {mean_mrr:.3f} below gate {MIN_MEAN_MRR}"


@pytest.mark.parametrize("case", ROUTING_CASES, ids=lambda case: case["id"])
def test_retrieval_routing_hints_golden_fixture(case: dict) -> None:
    assert is_document_grounded_query(case["query"]) == case["expect_document_grounded"]
    assert is_corpus_overview_query(case["query"]) == case["expect_corpus_overview"]


def test_retrieval_corpus_files_exist() -> None:
    corpus_dir = Path(__file__).resolve().parent / "fixtures" / "retrieval_corpus"
    for name in ("arthur-magazine.md", "philadelphia.md", "ops-runbook.md", "k8s-rollout.md"):
        assert (corpus_dir / name).is_file()
