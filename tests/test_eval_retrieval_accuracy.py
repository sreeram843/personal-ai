"""Retrieval golden-set evaluation (rerank/pack + routing hints)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.chat import RetrievedChunk
from app.services.information_routing import is_corpus_overview_query, is_document_grounded_query
from app.services.retrieval_rerank import rerank_and_pack

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval_golden.json"
GOLDEN_CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))
RERANK_CASES = [case for case in GOLDEN_CASES if case.get("candidates")]
ROUTING_CASES = [case for case in GOLDEN_CASES if "expect_document_grounded" in case]


@pytest.mark.parametrize("case", RERANK_CASES, ids=lambda case: case["id"])
def test_retrieval_rerank_golden_fixture(case: dict) -> None:
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
    packed_paths = [
        str((chunk.metadata or {}).get("path") or "")
        for chunk in packed
    ]
    for expected_path in case["expected_paths"]:
        assert expected_path in packed_paths, f"Expected {expected_path} in top-{case['top_k']}, got {packed_paths}"


@pytest.mark.parametrize("case", ROUTING_CASES, ids=lambda case: case["id"])
def test_retrieval_routing_hints_golden_fixture(case: dict) -> None:
    assert is_document_grounded_query(case["query"]) == case["expect_document_grounded"]
    assert is_corpus_overview_query(case["query"]) == case["expect_corpus_overview"]


def test_retrieval_corpus_files_exist() -> None:
    corpus_dir = Path(__file__).resolve().parent / "fixtures" / "retrieval_corpus"
    for name in ("arthur-magazine.md", "philadelphia.md"):
        assert (corpus_dir / name).is_file()
