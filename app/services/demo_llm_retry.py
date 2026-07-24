"""Retry helpers for demo LLM calls when the cloud provider rate-limits."""

from __future__ import annotations

import asyncio
import re
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")

PROVIDER_RATE_LIMIT_MESSAGE = (
    "The demo is temporarily rate-limited. Please wait a few seconds and try again."
)

_RETRY_AFTER_RE = re.compile(r"try again in\s+(\d+(?:\.\d+)?)\s*(ms|s|seconds?)", re.IGNORECASE)


def is_provider_rate_limit(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "(429)" in text
        or "rate_limit" in text
        or "rate limit" in text
        or "tokens per minute" in text
        or "tpm" in text and "limit" in text
    )


def provider_rate_limit_retry_delay_seconds(exc: BaseException, *, attempt: int) -> float:
    """Prefer provider-suggested wait; otherwise exponential backoff (~1s, 2s)."""
    match = _RETRY_AFTER_RE.search(str(exc))
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        seconds = value / 1000.0 if unit.startswith("ms") else value
        return max(0.25, min(seconds + 0.15, 5.0))
    return min(1.0 * (2**attempt), 4.0)


async def run_with_provider_rate_limit_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await operation()
        except Exception as exc:
            last_exc = exc
            if not is_provider_rate_limit(exc) or attempt >= max_attempts - 1:
                raise
            await asyncio.sleep(provider_rate_limit_retry_delay_seconds(exc, attempt=attempt))
    assert last_exc is not None
    raise last_exc


__all__ = [
    "PROVIDER_RATE_LIMIT_MESSAGE",
    "is_provider_rate_limit",
    "provider_rate_limit_retry_delay_seconds",
    "run_with_provider_rate_limit_retry",
]
