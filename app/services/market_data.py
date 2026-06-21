from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Protocol

import httpx

logger = logging.getLogger(__name__)


class MarketDataProvider(Protocol):
    async def get_stock_quote(self, ticker: str) -> dict | None:
        ...

    async def get_commodity_price(self, ticker: str) -> dict | None:
        ...


class YahooMarketDataProvider:
    """Default market data via Yahoo Finance chart API."""

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._headers = {"User-Agent": "Mozilla/5.0 (compatible; personal-ai-bot/1.0)"}

    async def get_stock_quote(self, ticker: str) -> dict | None:
        symbol = ticker.upper().strip()
        if not symbol:
            return None
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
                response = await client.get(url, params={"interval": "1m", "range": "1d"})
                response.raise_for_status()
                data = response.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev_close = meta.get("chartPreviousClose")
            if price is None:
                return None

            change = None
            change_pct = None
            if prev_close not in (None, 0):
                change = float(price) - float(prev_close)
                change_pct = (change / float(prev_close)) * 100.0

            market_time = meta.get("regularMarketTime")
            if market_time is not None:
                market_time_utc = datetime.fromtimestamp(int(market_time), tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
            else:
                market_time_utc = ""

            return {
                "ticker": symbol,
                "name": meta.get("longName") or meta.get("shortName") or symbol,
                "price": float(price),
                "currency": meta.get("currency", "USD"),
                "previous_close": float(prev_close) if prev_close is not None else None,
                "change": change,
                "change_percent": change_pct,
                "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "",
                "market_state": meta.get("marketState", ""),
                "market_time_utc": market_time_utc,
                "source": "Yahoo Finance",
            }
        except Exception as exc:
            logger.warning("Yahoo stock quote failed for %s: %s", symbol, exc)
            return None

    async def get_commodity_price(self, ticker: str) -> dict | None:
        quote = await self.get_stock_quote(ticker)
        if quote is None:
            return None
        return {
            "ticker": ticker.upper(),
            "price": quote["price"],
            "currency": quote.get("currency", "USD"),
            "source": "Yahoo Finance",
        }


class FinnhubMarketDataProvider:
    """Optional Finnhub provider when FINNHUB_API_KEY is configured."""

    def __init__(self, *, api_key: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    async def get_stock_quote(self, ticker: str) -> dict | None:
        symbol = ticker.upper().strip()
        if not symbol:
            return None
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": symbol, "token": self._api_key},
                )
                response.raise_for_status()
                payload = response.json()
            current = payload.get("c")
            if current is None:
                return None
            prev_close = payload.get("pc")
            change = None
            change_pct = None
            if prev_close not in (None, 0):
                change = float(current) - float(prev_close)
                change_pct = (change / float(prev_close)) * 100.0
            return {
                "ticker": symbol,
                "name": symbol,
                "price": float(current),
                "currency": "USD",
                "previous_close": float(prev_close) if prev_close is not None else None,
                "change": change,
                "change_percent": change_pct,
                "exchange": "",
                "market_state": "",
                "market_time_utc": "",
                "source": "Finnhub",
            }
        except Exception as exc:
            logger.warning("Finnhub quote failed for %s: %s", symbol, exc)
            return None

    async def get_commodity_price(self, ticker: str) -> dict | None:
        return await self.get_stock_quote(ticker)


def build_market_data_provider(*, provider: str, api_key: Optional[str] = None, timeout: float = 10.0) -> MarketDataProvider:
    normalized = (provider or "yahoo").strip().lower()
    if normalized == "finnhub":
        if not api_key:
            raise ValueError("FINNHUB_API_KEY is required when MARKET_DATA_PROVIDER=finnhub")
        return FinnhubMarketDataProvider(api_key=api_key, timeout=timeout)
    return YahooMarketDataProvider(timeout=timeout)


__all__ = [
    "MarketDataProvider",
    "YahooMarketDataProvider",
    "FinnhubMarketDataProvider",
    "build_market_data_provider",
]
