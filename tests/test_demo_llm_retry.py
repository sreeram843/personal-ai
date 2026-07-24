"""Tests for demo provider rate-limit detection and retry."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services.demo_llm_retry import (
    PROVIDER_RATE_LIMIT_MESSAGE,
    is_provider_rate_limit,
    provider_rate_limit_retry_delay_seconds,
    run_with_provider_rate_limit_retry,
)


def test_is_provider_rate_limit_detects_groq_tpm_error() -> None:
    exc = RuntimeError(
        "OpenAI-compatible provider request failed (429): "
        "{'error': {'message': 'Rate limit reached for model llama-3.1-8b-instant "
        "on tokens per minute (TPM): Limit 6000', 'code': 'rate_limit_exceeded'}}"
    )
    assert is_provider_rate_limit(exc) is True


def test_is_provider_rate_limit_ignores_generic_failures() -> None:
    assert is_provider_rate_limit(RuntimeError("connection reset")) is False
    assert is_provider_rate_limit(RuntimeError("Demo question limit reached.")) is False


def test_provider_rate_limit_retry_delay_parses_ms() -> None:
    exc = RuntimeError("Please try again in 970ms. Need more tokens?")
    delay = provider_rate_limit_retry_delay_seconds(exc, attempt=0)
    assert 0.9 <= delay <= 1.2


def test_run_with_provider_rate_limit_retry_succeeds_after_429() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("OpenAI-compatible provider request failed (429): rate_limit_exceeded")
        return "ok"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.demo_llm_retry.asyncio.sleep", AsyncMock())
        result = asyncio.run(run_with_provider_rate_limit_retry(flaky, max_attempts=3))

    assert result == "ok"
    assert calls["n"] == 3


def test_run_with_provider_rate_limit_retry_exhausts() -> None:
    async def always_429() -> str:
        raise RuntimeError("OpenAI-compatible provider request failed (429): rate limit")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.demo_llm_retry.asyncio.sleep", AsyncMock())
        with pytest.raises(RuntimeError, match="429"):
            asyncio.run(run_with_provider_rate_limit_retry(always_429, max_attempts=3))


def test_provider_rate_limit_message_is_user_friendly() -> None:
    assert "rate-limited" in PROVIDER_RATE_LIMIT_MESSAGE.lower()
    assert "try again" in PROVIDER_RATE_LIMIT_MESSAGE.lower()
