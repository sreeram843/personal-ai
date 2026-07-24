from __future__ import annotations

import logging
from typing import Optional

from app.core.config import Settings
from app.schemas.content_block import ContentBlock
from app.services.live_data_manager import LiveDataManager
from app.services.live_providers import (
    fetch_air_quality,
    fetch_crypto_price,
    fetch_service_status,
    fetch_sun_times,
    stub_provider_payload,
)
from app.services.live_tool_result import LiveToolResult
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)


class LiveToolHub:
    """Central broker: model picks tools, hub fetches/normalizes, cards ship separately."""

    def __init__(
        self,
        live_data: LiveDataManager,
        web_search: WebSearchService,
        settings: Settings,
    ) -> None:
        self._live = live_data
        self._web = web_search
        self._settings = settings

    async def _from_resolve(self, query: str) -> LiveToolResult:
        result = await self._live.resolve(query)
        if result is None:
            return LiveToolResult(
                summary="No structured live adapter matched this query. Try web_search for broader coverage.",
                block=None,
            )
        text, _ = self._live.render(result)
        blocks = self._live.to_blocks(result)
        return LiveToolResult(summary=text, block=blocks[0] if blocks else None)

    def _block(self, block_type: str, data: dict, *, subscription_key: Optional[str] = None) -> ContentBlock:
        return ContentBlock(type=block_type, data=data, subscription_key=subscription_key)

    def _fail(self, detail: str) -> LiveToolResult:
        return LiveToolResult(summary=f"ERROR: {detail}", block=None)

    async def get_fx_rate(self, query: str = "", user_query: str = "", base: str = "", quote: str = "") -> LiveToolResult:
        q = (query or user_query).strip()
        if base and quote:
            q = f"{base} to {quote}"
        if not q:
            return self._fail("FX tool requires a currency pair query")
        return await self._from_resolve(q)

    async def get_stock_price(self, query: str = "", user_query: str = "", ticker: str = "") -> LiveToolResult:
        q = (query or user_query).strip()
        if ticker:
            q = f"{ticker} stock price"
        if not q:
            return self._fail("Stock tool requires a ticker or query")
        return await self._from_resolve(q)

    async def get_commodity_price(self, query: str = "", user_query: str = "") -> LiveToolResult:
        q = (query or user_query).strip()
        if not q:
            return self._fail("Commodity tool requires a query")
        return await self._from_resolve(q)

    async def get_crypto_price(self, query: str = "", user_query: str = "", symbol: str = "") -> LiveToolResult:
        q = (query or user_query).strip()
        if symbol:
            q = f"{symbol} price"
        if not q:
            return self._fail("Crypto tool requires a symbol or query")
        payload = await fetch_crypto_price(q)
        if not payload:
            commodity = await self._from_resolve(q)
            if commodity.block and commodity.block.type in {"crypto", "commodity", "stock"}:
                return commodity
            return self._fail("LIVE DATA NOT VERIFIED for crypto query")
        block = self._block(
            "crypto",
            payload,
            subscription_key=payload.get("subscription_key"),
        )
        change = payload.get("change_percent")
        change_text = f" ({change:+.2f}% 24h)" if change is not None else ""
        summary = (
            f"**{payload['name']}** — **${payload['price']:,.2f} USD**{change_text}\n\n"
            f"Source: {payload['source']} · Fetched: {payload['asOf']}"
        )
        return LiveToolResult(summary=summary, block=block)

    async def get_weather(self, query: str = "", user_query: str = "", location: str = "") -> LiveToolResult:
        q = (query or user_query).strip()
        if location:
            q = f"weather in {location}"
        if not q:
            return self._fail("Weather tool requires a location or query")
        return await self._from_resolve(q)

    async def get_weather_forecast(
        self,
        query: str = "",
        user_query: str = "",
        location: str = "",
        days: int = 3,
    ) -> LiveToolResult:
        q = (query or user_query).strip()
        if location:
            q = f"{days}-day forecast for {location}"
        if not q:
            return self._fail("Forecast tool requires a location or query")
        return await self._from_resolve(q)

    async def get_news(self, query: str = "", user_query: str = "", topic: str = "") -> LiveToolResult:
        q = (query or user_query).strip()
        if topic:
            q = f"latest news on {topic}"
        if not q:
            return self._fail("News tool requires a topic or query")
        return await self._from_resolve(q)

    async def get_nearby_places(
        self,
        query: str = "",
        user_query: str = "",
        location: str = "",
        category: str = "",
    ) -> LiveToolResult:
        q = (query or user_query).strip()
        if location:
            q = f"{category or 'places'} in {location}".strip()
        if not q:
            return self._fail("Nearby places tool requires a location or query like 'coffee in Austin'")
        return await self._from_resolve(q)

    async def get_game_score(
        self,
        query: str = "",
        user_query: str = "",
        team: str = "",
        league: str = "nba",
    ) -> LiveToolResult:
        q = (query or user_query).strip()
        if team:
            q = f"{team} score {league}"
        if not q:
            return self._fail("Sports score tool requires a team or query")
        return await self._from_resolve(q)

    async def get_air_quality(self, query: str = "", user_query: str = "", location: str = "") -> LiveToolResult:
        loc = location.strip() or (query or user_query).strip()
        if not loc:
            return self._fail("Air quality tool requires a location")
        payload = await fetch_air_quality(loc)
        if not payload:
            return self._fail(f"Unable to fetch air quality for '{loc}'")
        block = self._block("air_quality", payload)
        aqi = payload.get("usAqi")
        summary = f"**{payload['location']}** — US AQI **{aqi}** (PM2.5 {payload.get('pm25')} µg/m³)"
        return LiveToolResult(summary=summary, block=block)

    async def get_sun_times(self, query: str = "", user_query: str = "", location: str = "") -> LiveToolResult:
        loc = location.strip() or (query or user_query).strip()
        if not loc:
            return self._fail("Sun times tool requires a location")
        payload = await fetch_sun_times(loc)
        if not payload:
            return self._fail(f"Unable to fetch sun times for '{loc}'")
        block = self._block("sun_times", payload)
        summary = (
            f"**{payload['location']}** — sunrise {payload.get('sunrise')} · "
            f"sunset {payload.get('sunset')}"
        )
        return LiveToolResult(summary=summary, block=block)

    async def get_service_status(self, query: str = "", user_query: str = "", service: str = "") -> LiveToolResult:
        svc = service.strip() or (query or user_query).strip()
        if not svc:
            return self._fail("Service status tool requires a service name (e.g. github, aws)")
        payload = await fetch_service_status(svc)
        if not payload:
            return self._fail(f"No status feed configured for '{svc}'")
        block = self._block("service_status", payload)
        summary = f"**{payload['service']}** — {payload.get('description', payload.get('status'))}"
        return LiveToolResult(summary=summary, block=block)

    async def get_flight_status(
        self,
        query: str = "",
        user_query: str = "",
        flight_number: str = "",
    ) -> LiveToolResult:
        ref = flight_number.strip() or (query or user_query).strip()
        payload = stub_provider_payload(
            "flight",
            ref,
            note="Flight tracking requires a FlightAware or AviationStack API key. Use web_search meanwhile.",
        )
        block = self._block("flight", payload)
        return LiveToolResult(summary=payload["message"], block=block)

    async def get_package_tracking(
        self,
        query: str = "",
        user_query: str = "",
        tracking_number: str = "",
    ) -> LiveToolResult:
        ref = tracking_number.strip() or (query or user_query).strip()
        payload = stub_provider_payload(
            "package",
            ref,
            note="Package tracking requires a carrier API key (AfterShip/Shippo). Use web_search meanwhile.",
        )
        block = self._block("package", payload)
        return LiveToolResult(summary=payload["message"], block=block)

    async def get_transit_arrivals(
        self,
        query: str = "",
        user_query: str = "",
        stop_id: str = "",
    ) -> LiveToolResult:
        ref = stop_id.strip() or (query or user_query).strip()
        payload = stub_provider_payload(
            "transit",
            ref,
            note="Transit realtime feeds require GTFS-RT configuration. Use web_search meanwhile.",
        )
        block = self._block("transit", payload)
        return LiveToolResult(summary=payload["message"], block=block)

    async def get_traffic_eta(
        self,
        query: str = "",
        user_query: str = "",
        origin: str = "",
        destination: str = "",
    ) -> LiveToolResult:
        ref = (query or user_query).strip() or f"{origin} to {destination}".strip()
        payload = stub_provider_payload(
            "traffic",
            ref,
            note="Live traffic ETA requires Google Maps or Mapbox credentials. Use web_search meanwhile.",
        )
        block = self._block("traffic", payload)
        return LiveToolResult(summary=payload["message"], block=block)

    async def get_gas_price(self, query: str = "", user_query: str = "", location: str = "") -> LiveToolResult:
        loc = location.strip() or (query or user_query).strip()
        payload = stub_provider_payload(
            "gas_price",
            loc,
            note="Gas price feeds require a regional data provider. Use web_search meanwhile.",
        )
        block = self._block("gas_price", payload)
        return LiveToolResult(summary=payload["message"], block=block)

    async def get_betting_odds(self, query: str = "", user_query: str = "", event: str = "") -> LiveToolResult:
        ref = event.strip() or (query or user_query).strip()
        payload = stub_provider_payload(
            "odds",
            ref,
            note="Betting odds require The Odds API or similar credentials. Use web_search meanwhile.",
        )
        block = self._block("odds", payload)
        return LiveToolResult(summary=payload["message"], block=block)

    async def get_election_results(self, query: str = "", user_query: str = "", race: str = "") -> LiveToolResult:
        ref = race.strip() or (query or user_query).strip()
        payload = stub_provider_payload(
            "election",
            ref,
            note="Election results require AP Elections or news API access. Use web_search meanwhile.",
        )
        block = self._block("election", payload)
        return LiveToolResult(summary=payload["message"], block=block)


__all__ = ["LiveToolHub"]
