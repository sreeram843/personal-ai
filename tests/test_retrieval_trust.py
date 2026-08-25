"""Per-user retrieval trust isolation and rerank weighting."""

from __future__ import annotations

import pytest

from app.schemas.chat import RetrievedChunk
from app.services.retrieval_rerank import hybrid_rerank_score, rerank_and_pack
from app.services.retrieval_trust import record_reviewer_verdict, trust_multiplier

USER_PAIRS = [
    ("user-alpha", "user-beta"),
    ("tenant-1", "tenant-2"),
    ("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"),
]


def _chunk(chunk_id: str, path: str, text: str, score: float = 0.8) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id,
        score=score,
        text=text,
        metadata={"path": path, "name": path.rsplit("/", 1)[-1]},
    )


@pytest.mark.parametrize("user_a,user_b", USER_PAIRS)
def test_retrieval_trust_never_leaks_across_users(user_a: str, user_b: str) -> None:
    source = "docs/secret.md"
    record_reviewer_verdict(user_a, [source], f"{source} is unsupported and cannot verify the claims.")
    record_reviewer_verdict(user_a, [source], f"{source} is unverified and weak.")
    record_reviewer_verdict(user_a, [source], f"{source} remains unsupported.")

    assert trust_multiplier(user_a, source) < 1.0
    assert 0.5 < trust_multiplier(user_a, source) < 1.15
    assert trust_multiplier(user_b, source) == 1.0

    record_reviewer_verdict(user_b, [source], f"{source} supports the draft.")
    assert trust_multiplier(user_b, source) > 1.0
    assert trust_multiplier(user_a, source) < trust_multiplier(user_b, source)


def test_unmentioned_source_gets_weak_accept_when_review_is_positive() -> None:
    source = "docs/ops-runbook.md"
    assert trust_multiplier("user-pos", source) == 1.0
    record_reviewer_verdict("user-pos", [source], "The draft is accurate and well supported.")
    assert trust_multiplier("user-pos", source) > 1.0


def test_unmentioned_source_skipped_when_review_is_negative() -> None:
    source = "docs/skipped.md"
    record_reviewer_verdict("user-neg", [source], "This draft has unsupported claims overall.")
    assert trust_multiplier("user-neg", source) == 1.0


def test_trust_multiplier_stays_in_open_interval() -> None:
    source = "docs/bounded.md"
    assert trust_multiplier("user-bound", source) == 1.0
    for _ in range(8):
        record_reviewer_verdict("user-bound", [source], f"{source} is unsupported and unverified.")
    multiplier = trust_multiplier("user-bound", source)
    assert 0.5 < multiplier < 1.15
    assert multiplier < 1.0


def test_hybrid_rerank_score_drops_after_repeated_rejects() -> None:
    user_id = "user-rerank"
    path = "docs/finance.md"
    chunk = _chunk("doc-1", path, "budget forecast Q3 revenue increased twelve percent")
    before = hybrid_rerank_score(
        query="budget forecast Q3 revenue",
        chunk=chunk,
        normalized_vector_score=1.0,
        user_id=user_id,
    )
    for _ in range(6):
        record_reviewer_verdict(user_id, [path], f"{path} is unsupported and cannot verify.")
    after = hybrid_rerank_score(
        query="budget forecast Q3 revenue",
        chunk=chunk,
        normalized_vector_score=1.0,
        user_id=user_id,
    )
    assert after < before
    assert 0.5 < trust_multiplier(user_id, path) < 1.0


def test_rerank_and_pack_demotes_repeatedly_rejected_source() -> None:
    user_id = "user-pack"
    trusted_path = "docs/trusted.md"
    rejected_path = "docs/rejected.md"
    query = "deployment checklist"
    candidates = [
        _chunk("rejected", rejected_path, "deployment checklist step one verify config", score=0.95),
        _chunk("trusted", trusted_path, "deployment checklist step one verify config", score=0.94),
        _chunk("noise", "docs/noise.md", "cafeteria menu updates", score=0.50),
    ]
    for _ in range(8):
        record_reviewer_verdict(user_id, [rejected_path], f"{rejected_path} is unsupported and unverified.")

    packed = rerank_and_pack(query, candidates, limit=1, user_id=user_id)
    assert packed[0].id == "trusted"
