"""Tests for optional cross-encoder rerank blending."""

from __future__ import annotations

import asyncio
import threading

import httpx

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk
from app.services import cross_encoder_rerank
from app.services.cross_encoder_rerank import blend_cross_encoder_scores, score_with_cross_encoder
from app.services.retrieval_rerank import rerank_and_pack


def _chunk(chunk_id: str, score: float, text: str) -> RetrievedChunk:
    return RetrievedChunk(id=chunk_id, score=score, text=text, metadata={"path": f"{chunk_id}.md"})


def test_blend_cross_encoder_scores_prefers_ce_when_weight_high() -> None:
    blended = blend_cross_encoder_scores(
        hybrid_scores=[0.9, 0.1],
        cross_encoder_scores=[0.1, 0.9],
        cross_encoder_weight=1.0,
    )
    assert blended[1] > blended[0]


def test_rerank_and_pack_uses_cross_encoder_scores() -> None:
    query = "budget forecast"
    candidates = [
        _chunk("weak", 0.99, "generic company overview"),
        _chunk("strong", 0.40, "budget forecast revenue rose"),
    ]
    # CE strongly prefers the second candidate.
    packed = rerank_and_pack(
        query,
        candidates,
        limit=1,
        cross_encoder_scores=[0.05, 0.95],
        cross_encoder_weight=1.0,
    )
    assert packed[0].id == "strong"


def test_score_with_cross_encoder_http(monkeypatch) -> None:
    settings = Settings(
        retrieval_cross_encoder_enabled=True,
        retrieval_cross_encoder_provider="http",
        retrieval_cross_encoder_url="http://reranker.test",
        retrieval_cross_encoder_model="BAAI/bge-reranker-base",
    )
    candidates = [_chunk("a", 0.5, "alpha"), _chunk("b", 0.4, "beta")]

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"results": [{"index": 0, "score": 0.2}, {"index": 1, "score": 0.8}]}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None, headers=None):
            assert url.endswith("/rerank")
            assert json["query"] == "q"
            assert json["texts"] == ["alpha", "beta"]
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    scores = asyncio.run(score_with_cross_encoder("q", candidates, settings=settings))
    assert scores == [0.2, 0.8]


def test_score_with_cross_encoder_disabled_returns_none() -> None:
    settings = Settings(retrieval_cross_encoder_enabled=False)
    scores = asyncio.run(score_with_cross_encoder("q", [_chunk("a", 0.5, "x")], settings=settings))
    assert scores is None


def test_score_with_cross_encoder_local_runs_off_the_event_loop(monkeypatch) -> None:
    """
    _score_local is a synchronous, potentially seconds-long CPU forward pass;
    it must run via asyncio.to_thread rather than inline on the caller's event
    loop, or it would stall every other in-flight request.
    """
    settings = Settings(
        retrieval_cross_encoder_enabled=True,
        retrieval_cross_encoder_provider="local",
        retrieval_cross_encoder_model="stub-model",
    )
    candidates = [_chunk("a", 0.5, "alpha"), _chunk("b", 0.4, "beta")]
    main_thread = threading.current_thread()
    seen_threads: list[threading.Thread] = []

    def _fake_score_local(query, texts, *, settings):
        seen_threads.append(threading.current_thread())
        return [0.3, 0.7]

    monkeypatch.setattr(cross_encoder_rerank, "_score_local", _fake_score_local)
    scores = asyncio.run(score_with_cross_encoder("q", candidates, settings=settings))

    assert scores == [0.3, 0.7]
    assert seen_threads, "_score_local was never called"
    assert seen_threads[0] is not main_thread
