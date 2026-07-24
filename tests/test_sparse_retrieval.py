"""Tests for sparse/keyword hybrid retrieval helpers."""

from __future__ import annotations

from app.services.sparse_retrieval import (
    merge_dense_and_keyword_hits,
    significant_query_terms,
    text_to_sparse_indices,
    tokenize_for_sparse,
)


class _Hit:
    def __init__(self, hit_id: str, score: float, text: str) -> None:
        self.id = hit_id
        self.score = score
        self.payload = {"text": text, "path": f"{hit_id}.md"}


def test_tokenize_and_significant_terms() -> None:
    terms = significant_query_terms("the kubernetes deployment rollout strategy")
    assert "kubernetes" in terms
    assert "the" not in tokenize_for_sparse("the kubernetes")


def test_text_to_sparse_indices_stable() -> None:
    left = text_to_sparse_indices("budget forecast revenue")
    right = text_to_sparse_indices("budget forecast revenue")
    assert left == right
    assert left[0]
    assert len(left[0]) == len(left[1])


def test_merge_dense_and_keyword_hits_adds_keyword_only() -> None:
    dense = [_Hit("dense-1", 0.9, "generic overview")]
    keyword = [
        _Hit("dense-1", 0.0, "generic overview"),
        _Hit("kw-only", 0.0, "kubernetes deployment rollout strategy checklist"),
    ]
    merged = merge_dense_and_keyword_hits(
        query="kubernetes deployment rollout",
        dense_hits=dense,
        keyword_hits=keyword,
    )
    ids = {str(item.id) for item in merged}
    assert ids == {"dense-1", "kw-only"}
    kw_hit = next(item for item in merged if str(item.id) == "kw-only")
    assert float(kw_hit.score) >= 0.35
