"""Prometheus metrics for model inference and chat reply timing."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from prometheus_client import Counter, Histogram

# How long each call to the language model takes (one generation).
MODEL_CALLS_TOTAL = Counter(
    "model_calls_total",
    "Total calls to the language model",
    ["provider", "model", "status"],
)

MODEL_RESPONSE_SECONDS = Histogram(
    "model_response_seconds",
    "Seconds for one model call to complete",
    ["provider", "model"],
    buckets=(0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# End-to-end time until the user gets a full assistant reply.
CHAT_REPLIES_TOTAL = Counter(
    "chat_replies_total",
    "Total chat requests that returned an assistant reply",
    ["mode", "status"],
)

CHAT_REPLY_SECONDS = Histogram(
    "chat_reply_seconds",
    "Seconds from user send to full assistant reply",
    ["mode"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)


def _normalize_model(model: str) -> str:
    value = (model or "unknown").strip()
    return value or "unknown"


@asynccontextmanager
async def observe_llm_call(*, provider: str, model: str) -> AsyncIterator[None]:
    """Record model response time and success/error for one inference call."""
    started = time.perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.perf_counter() - started
        model_label = _normalize_model(model)
        provider_label = (provider or "unknown").strip() or "unknown"
        MODEL_CALLS_TOTAL.labels(
            provider=provider_label,
            model=model_label,
            status=status,
        ).inc()
        MODEL_RESPONSE_SECONDS.labels(provider=provider_label, model=model_label).observe(elapsed)


@asynccontextmanager
async def observe_chat_request(*, mode: str) -> AsyncIterator[None]:
    """Record end-to-end chat reply time for a persisted chat handler."""
    started = time.perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.perf_counter() - started
        mode_label = (mode or "unknown").strip() or "unknown"
        CHAT_REPLIES_TOTAL.labels(mode=mode_label, status=status).inc()
        CHAT_REPLY_SECONDS.labels(mode=mode_label).observe(elapsed)
