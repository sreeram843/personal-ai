"""Optional cross-encoder reranking (HTTP TEI/Cohere-style or local sentence-transformers)."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Sequence

import httpx

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk

logger = logging.getLogger(__name__)


async def score_with_cross_encoder(
    query: str,
    candidates: Sequence[RetrievedChunk],
    *,
    settings: Settings,
) -> Optional[List[float]]:
    """
    Return one relevance score per candidate, or None to skip cross-encoder.

    Supports:
    - provider=http: TEI-compatible POST {query, texts} → {results:[{index,score}]}
    - provider=local: optional sentence-transformers CrossEncoder (heavy; opt-in)
    """
    if not settings.retrieval_cross_encoder_enabled or not candidates:
        return None

    provider = (settings.retrieval_cross_encoder_provider or "http").strip().lower()
    if provider in {"", "none", "off", "hybrid"}:
        return None

    texts = [candidate.text for candidate in candidates]
    try:
        if provider == "http":
            return await _score_http(query, texts, settings=settings)
        if provider == "local":
            # _score_local runs a synchronous CPU-bound forward pass (potentially
            # seconds on CPU); offload it so it doesn't block the event loop for
            # every other in-flight request.
            return await asyncio.to_thread(_score_local, query, texts, settings=settings)
    except Exception:
        logger.exception("Cross-encoder rerank failed; falling back to hybrid lexical scores")
        return None

    logger.warning("Unknown cross-encoder provider %r; skipping", provider)
    return None


async def _score_http(query: str, texts: Sequence[str], *, settings: Settings) -> List[float]:
    base_url = (settings.retrieval_cross_encoder_url or "").rstrip("/")
    if not base_url:
        raise ValueError("retrieval_cross_encoder_url is required when provider=http")

    payload = {
        "query": query,
        "texts": list(texts),
        "model": settings.retrieval_cross_encoder_model,
    }
    headers = {"Content-Type": "application/json"}
    if settings.retrieval_cross_encoder_api_key:
        headers["Authorization"] = f"Bearer {settings.retrieval_cross_encoder_api_key}"

    timeout = httpx.Timeout(settings.retrieval_cross_encoder_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{base_url}/rerank", json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    scores = [0.0] * len(texts)
    results = body.get("results") if isinstance(body, dict) else body
    if isinstance(body, dict) and "scores" in body and isinstance(body["scores"], list):
        raw_scores = [float(value) for value in body["scores"]]
        if len(raw_scores) != len(texts):
            raise ValueError("cross-encoder score count mismatch")
        return raw_scores

    if not isinstance(results, list):
        raise ValueError("unexpected cross-encoder response shape")

    for item in results:
        if not isinstance(item, dict):
            continue
        index = int(item.get("index", -1))
        if 0 <= index < len(scores):
            scores[index] = float(item.get("score") or item.get("relevance_score") or 0.0)
    return scores


def _score_local(query: str, texts: Sequence[str], *, settings: Settings) -> List[float]:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Local cross-encoder requires sentence-transformers. "
            "Install it or set RETRIEVAL_CROSS_ENCODER_PROVIDER=http."
        ) from exc

    model_name = settings.retrieval_cross_encoder_model or "BAAI/bge-reranker-base"
    # Cache on the function to avoid reloading the model every call.
    cache_key = "_cached_model"
    model = getattr(_score_local, cache_key, None)
    if model is None or getattr(model, "_model_name", None) != model_name:
        model = CrossEncoder(model_name)
        setattr(model, "_model_name", model_name)
        setattr(_score_local, cache_key, model)

    pairs = [(query, text) for text in texts]
    raw = model.predict(pairs)
    return [float(score) for score in raw]


def blend_cross_encoder_scores(
    *,
    hybrid_scores: Sequence[float],
    cross_encoder_scores: Sequence[float],
    cross_encoder_weight: float,
) -> List[float]:
    """Blend normalized hybrid and cross-encoder scores."""
    if len(hybrid_scores) != len(cross_encoder_scores):
        raise ValueError("score length mismatch")
    weight = min(1.0, max(0.0, cross_encoder_weight))
    if weight <= 0:
        return list(hybrid_scores)
    if weight >= 1:
        return _minmax(cross_encoder_scores)

    hybrid_norm = _minmax(hybrid_scores)
    ce_norm = _minmax(cross_encoder_scores)
    return [
        ((1.0 - weight) * hybrid) + (weight * ce)
        for hybrid, ce in zip(hybrid_norm, ce_norm)
    ]


def _minmax(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if maximum <= minimum:
        return [1.0 for _ in values]
    span = maximum - minimum
    return [(value - minimum) / span for value in values]


__all__ = [
    "blend_cross_encoder_scores",
    "score_with_cross_encoder",
]
