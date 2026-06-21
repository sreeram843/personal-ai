"""Market data provider tests."""

from __future__ import annotations

import asyncio

from app.services.market_data import YahooMarketDataProvider, build_market_data_provider


def test_build_market_data_provider_defaults_to_yahoo() -> None:
    provider = build_market_data_provider(provider="yahoo", api_key=None)
    assert provider.__class__.__name__ == "YahooMarketDataProvider"


def test_yahoo_provider_parses_chart_payload(monkeypatch) -> None:
    provider = YahooMarketDataProvider(timeout=5)

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "regularMarketPrice": 420.5,
                                "chartPreviousClose": 418.0,
                                "currency": "USD",
                                "longName": "Microsoft Corporation",
                                "regularMarketTime": 1_700_000_000,
                                "marketState": "REGULAR",
                                "fullExchangeName": "NasdaqGS",
                            }
                        }
                    ]
                }
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            return _Resp()

    monkeypatch.setattr("app.services.market_data.httpx.AsyncClient", lambda **kwargs: _Client())

    quote = asyncio.run(provider.get_stock_quote("MSFT"))
    assert quote is not None
    assert quote["ticker"] == "MSFT"
    assert quote["price"] == 420.5
    assert quote["source"] == "Yahoo Finance"
