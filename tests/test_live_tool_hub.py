"""Tests for live tool hub and block collection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.content_block import ContentBlock
from app.services.live_block_collector import append_live_block, get_live_blocks, reset_live_blocks, restore_live_blocks
from app.services.live_tool_hub import LiveToolHub
from app.services.live_tool_result import LiveToolResult


@pytest.mark.asyncio
async def test_live_block_collector_roundtrip() -> None:
    token = reset_live_blocks()
    try:
        append_live_block(ContentBlock(type="fx", data={"base": "USD", "quote": "INR", "rate": 83.0}))
        blocks = get_live_blocks()
        assert len(blocks) == 1
        assert blocks[0].type == "fx"
    finally:
        restore_live_blocks(token)


@pytest.mark.asyncio
async def test_live_tool_hub_appends_via_executor_pattern() -> None:
    live_data = MagicMock()
    live_data.resolve = AsyncMock(return_value=None)
    hub = LiveToolHub(live_data=live_data, web_search=MagicMock(), settings=MagicMock())

    token = reset_live_blocks()
    try:
        result = await hub.get_flight_status(flight_number="UA123")
        assert "FlightAware" in result.summary or "web_search" in result.summary
        assert result.block is not None
        append_live_block(result.block)
        assert get_live_blocks()[0].type == "flight"
    finally:
        restore_live_blocks(token)


@pytest.mark.asyncio
async def test_live_tool_hub_crypto_builds_block(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(query: str, *, timeout: float = 10.0):
        return {
            "symbol": "BTC",
            "name": "BTC",
            "price": 65000.0,
            "currency": "USD",
            "change_percent": 1.5,
            "asOf": "2026-06-26T12:00:00Z",
            "source": "CoinGecko",
            "live": True,
            "subscription_key": "crypto:BTC",
        }

    monkeypatch.setattr("app.services.live_providers.fetch_crypto_price", fake_fetch)
    hub = LiveToolHub(live_data=MagicMock(), web_search=MagicMock(), settings=MagicMock())
    result = await hub.get_crypto_price(symbol="BTC")
    assert isinstance(result, LiveToolResult)
    assert result.block is not None
    assert result.block.type == "crypto"
    assert "65" in result.summary
