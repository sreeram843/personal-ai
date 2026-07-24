from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Optional, Sequence, Tuple

from prometheus_client import Counter, Histogram

from app.core.config import Settings
from app.schemas.adapter import AdapterResult
from app.schemas.content_block import ContentBlock
from app.schemas.live_intent import LiveDataProvenance, LiveIntent
from app.services.adapter_cache import AdapterCache
from app.services.live_intent_router import is_structured_live_intent, route_live_intent
from app.services.local_places import fetch_nearby_places, location_prompt_text
from app.services.llm_gateway import StageModelConfig
from app.services.sports_data import SportsDataService
from app.services.web_search import WEATHER_CODE_LABELS, WebSearchService

logger = logging.getLogger(__name__)


def _meta_footer(source: str, fetched_at: str) -> str:
    return f"Source: {source} · Fetched: {fetched_at}"


def _weather_label(code: object) -> str:
    if code is None:
        return "Unknown condition"
    try:
        return WEATHER_CODE_LABELS.get(int(code), "Unknown condition")
    except (TypeError, ValueError):
        return "Unknown condition"


def _format_day_label(date_str: str) -> str:
    try:
        day = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        return day.strftime("%a, %b %d").replace(" 0", " ")
    except ValueError:
        return str(date_str)


def _format_temp_range(min_temp: object, max_temp: object, unit: str) -> str:
    unit = unit or "°C"
    if min_temp is not None and max_temp is not None:
        return f"{float(min_temp):.0f}–{float(max_temp):.0f} {unit}"
    if max_temp is not None:
        return f"high {float(max_temp):.0f} {unit}"
    if min_temp is not None:
        return f"low {float(min_temp):.0f} {unit}"
    return ""


def _format_news_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        normalized = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return iso[:10] if len(iso) >= 10 else iso

ADAPTER_REQUESTS_TOTAL = Counter(
    "live_adapter_requests_total",
    "Total adapter requests",
    ["domain", "status", "source", "cache_hit"],
)

ADAPTER_LATENCY_SECONDS = Histogram(
    "live_adapter_latency_seconds",
    "Latency of live adapter calls",
    ["domain", "source"],
)


class LiveDataManager:
    """Unified adapter manager with normalized responses, cache, and metrics."""

    def __init__(
        self,
        web_search: WebSearchService,
        cache: AdapterCache,
        settings: Settings,
        sports: SportsDataService | None = None,
    ) -> None:
        self._web = web_search
        self._cache = cache
        self._settings = settings
        self._sports = sports or SportsDataService()

    @staticmethod
    def _now_utc() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _domain_ttl(self, domain: str) -> int:
        mapping = {
            "fx": self._settings.live_cache_ttl_fx_seconds,
            "commodity": self._settings.live_cache_ttl_commodity_seconds,
            "stock": self._settings.live_cache_ttl_stock_seconds,
            "weather_current": self._settings.live_cache_ttl_weather_current_seconds,
            "weather_forecast": self._settings.live_cache_ttl_weather_forecast_seconds,
            "news": self._settings.live_cache_ttl_news_seconds,
            "game_score": self._settings.live_cache_ttl_sports_seconds,
            "nearby_places": self._settings.live_cache_ttl_nearby_places_seconds,
        }
        return mapping.get(domain, self._settings.adapter_cache_default_ttl_seconds)

    @staticmethod
    def to_provenance(result: AdapterResult) -> LiveDataProvenance:
        return LiveDataProvenance(
            domain=result.domain,
            source=result.source,
            fetched_at_utc=result.fetched_at_utc,
            confidence=result.confidence,
            verified=result.verified,
            provider_timestamp=result.provider_timestamp,
        )

    @staticmethod
    def to_blocks(result: AdapterResult) -> list[ContentBlock]:
        """Map a verified adapter result to structured UI blocks."""
        blocks = LiveDataManager._map_verified_blocks(result)
        for block in blocks:
            block.data.setdefault("confidence", float(result.confidence))
        return blocks

    @staticmethod
    def _map_verified_blocks(result: AdapterResult) -> list[ContentBlock]:
        if result.status != "ok" or not result.verified:
            return []

        data = result.data or {}
        subscription_key = data.get("subscription_key")

        if result.domain == "stock":
            change = data.get("change")
            change_pct = data.get("change_percent")
            market_state = str(data.get("market_state") or "").lower()
            is_delayed = market_state not in {"", "regular", "open", "trading"}
            return [
                ContentBlock(
                    type="stock",
                    subscription_key=f"stock:{data.get('ticker', '')}" if market_state in {"regular", "open", "trading"} else None,
                    data={
                        "ticker": data.get("ticker", ""),
                        "name": data.get("name", ""),
                        "price": data.get("price"),
                        "currency": data.get("currency", "USD"),
                        "change": change,
                        "changePercent": change_pct,
                        "previousClose": data.get("previous_close"),
                        "exchange": data.get("exchange", ""),
                        "marketState": data.get("market_state", ""),
                        "delayed": is_delayed,
                        "asOf": result.provider_timestamp or result.fetched_at_utc,
                        "source": result.source,
                        "live": market_state in {"regular", "open", "trading"},
                    },
                )
            ]

        if result.domain == "weather_current":
            return [
                ContentBlock(
                    type="weather",
                    data={
                        "mode": "current",
                        "location": data.get("location", ""),
                        "condition": _weather_label(data.get("weather_code")),
                        "temperature": data.get("temperature"),
                        "temperatureUnit": data.get("temperature_unit", "°C"),
                        "feelsLike": data.get("feels_like"),
                        "humidity": data.get("humidity"),
                        "humidityUnit": data.get("humidity_unit", "%"),
                        "windSpeed": data.get("wind_speed"),
                        "windSpeedUnit": data.get("wind_speed_unit", "km/h"),
                        "precipitation": data.get("precipitation"),
                        "precipitationUnit": data.get("precipitation_unit", "mm"),
                        "asOf": data.get("time") or result.fetched_at_utc,
                        "source": result.source,
                        "live": False,
                    },
                )
            ]

        if result.domain == "weather_forecast":
            return [
                ContentBlock(
                    type="weather",
                    data={
                        "mode": "forecast",
                        "location": data.get("location", ""),
                        "days": data.get("days", []),
                        "tempUnit": data.get("temp_unit", "°C"),
                        "precipUnit": data.get("precip_unit", "mm"),
                        "windUnit": data.get("wind_unit", "km/h"),
                        "asOf": result.fetched_at_utc,
                        "source": result.source,
                        "live": False,
                    },
                )
            ]

        if result.domain == "game_score":
            block_data = {
                "league": data.get("league", ""),
                "homeTeam": data.get("home_team", ""),
                "awayTeam": data.get("away_team", ""),
                "homeAbbrev": data.get("home_abbrev", ""),
                "awayAbbrev": data.get("away_abbrev", ""),
                "homeScore": data.get("home_score"),
                "awayScore": data.get("away_score"),
                "homeScoreDisplay": data.get("home_score_display"),
                "awayScoreDisplay": data.get("away_score_display"),
                "sport": data.get("sport", "default"),
                "matchFormat": data.get("match_format", ""),
                "venue": data.get("venue", ""),
                "status": data.get("status", ""),
                "period": data.get("period", ""),
                "clock": data.get("clock", ""),
                "isLive": bool(data.get("is_live")),
                "asOf": data.get("fetched_at_utc") or result.fetched_at_utc,
                "source": result.source,
                "live": bool(data.get("is_live")),
            }
            return [
                ContentBlock(
                    type="game_score",
                    subscription_key=subscription_key,
                    data=block_data,
                )
            ]

        if result.domain == "fx":
            return [
                ContentBlock(
                    type="fx",
                    data={
                        "base": data.get("base", ""),
                        "quote": data.get("quote", ""),
                        "rate": data.get("rate"),
                        "date": data.get("date", ""),
                        "asOf": result.provider_timestamp or result.fetched_at_utc,
                        "source": result.source,
                        "live": False,
                    },
                )
            ]

        if result.domain == "commodity":
            ticker = str(data.get("ticker") or "")
            label = str(data.get("label") or ticker)
            is_crypto = ticker in {"BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "XRP-USD", "ADA-USD"}
            block_type = "crypto" if is_crypto else "commodity"
            return [
                ContentBlock(
                    type=block_type,
                    subscription_key=f"crypto:{label}" if is_crypto else None,
                    data={
                        "ticker": ticker,
                        "name": label,
                        "price": data.get("price"),
                        "currency": data.get("currency", "USD"),
                        "asOf": result.fetched_at_utc,
                        "source": result.source,
                        "live": is_crypto,
                    },
                )
            ]

        if result.domain == "news":
            return [
                ContentBlock(
                    type="news",
                    data={
                        "topic": data.get("topic", ""),
                        "headlines": data.get("headlines", []),
                        "asOf": result.fetched_at_utc,
                        "source": result.source,
                        "live": False,
                    },
                )
            ]

        if result.domain == "nearby_places":
            return [
                ContentBlock(
                    type="nearby_places",
                    data={
                        "location": data.get("location", ""),
                        "category": data.get("category", "general"),
                        "categoryLabel": data.get("categoryLabel", "nearby places"),
                        "radiusKm": data.get("radiusKm"),
                        "places": data.get("places", []),
                        "asOf": result.fetched_at_utc,
                        "source": result.source,
                        "live": False,
                    },
                )
            ]

        return []

    @staticmethod
    def companion_message(result: AdapterResult) -> str:
        """Short prose paired with structured cards — the card carries the numbers."""
        if result.status != "ok" or not result.verified:
            text, _ = LiveDataManager.render(result)
            return text

        data = result.data or {}
        if result.domain == "stock":
            name = data.get("name") or data.get("ticker") or "this stock"
            ticker = data.get("ticker") or ""
            label = f"**{name} ({ticker})**" if ticker else f"**{name}**"
            return f"Here's the latest quote for {label}."
        if result.domain == "commodity":
            label = data.get("label") or data.get("ticker") or "this asset"
            return f"Here's the latest price for **{label}**."
        if result.domain == "fx":
            base = data.get("base", "")
            quote = data.get("quote", "")
            return f"Here's the live **{base}/{quote}** rate."
        if result.domain == "weather_current":
            location = data.get("location") or "that location"
            return f"Current conditions for **{location}**."
        if result.domain == "weather_forecast":
            location = data.get("location") or "that location"
            days = len(data.get("days") or [])
            return f"{days}-day forecast for **{location}**."
        if result.domain == "news":
            topic = data.get("topic") or "the news"
            return f"Latest headlines on **{topic}**."
        if result.domain == "game_score":
            away = data.get("away_team") or "Away"
            home = data.get("home_team") or "Home"
            if data.get("sport") == "cricket":
                away_line = data.get("away_score_display") or str(data.get("away_score", ""))
                home_line = data.get("home_score_display") or str(data.get("home_score", ""))
                fmt = data.get("match_format") or "Cricket"
                return f"Score update: **{away} {away_line}** vs **{home} {home_line}** ({fmt})."
            return f"Score update: **{away}** at **{home}**."
        if result.domain == "nearby_places":
            location = data.get("location") or "that area"
            label = data.get("categoryLabel") or "nearby places"
            count = len(data.get("places") or [])
            return f"Here are **{count} {label}** near **{location}**."
        return "Here's the latest live data."

    def is_live_intent_query(self, query: str) -> bool:
        return route_live_intent(query) is not None

    @staticmethod
    def is_only_generic_freshness_live_intent(query: str) -> bool:
        """
        True when the only live signal is the generic freshness word list (e.g. 'tomorrow',
        'latest') and not a type our deterministic adapters cover (fx, weather, news, …).

        These questions should *not* short-circuit to LIVE_DATA_NOT_VERIFIED; the orchestrator
        can use web search + the model (e.g. IPL schedules, sports, product releases).
        """
        text = query.strip()
        intent = route_live_intent(text)
        return intent is not None and intent.domain == "generic_fresh"

    def unresolved_live_intent_result(self) -> AdapterResult:
        """Return a deterministic guardrail result when live verification fails."""
        return AdapterResult(
            domain="live_query",
            status="error",
            verified=False,
            source="Live Adapter Router",
            fetched_at_utc=self._now_utc(),
            ttl_seconds=10,
            error_code="LIVE_DATA_NOT_VERIFIED",
            error_message="No adapter produced verifiable live data",
        )

    async def resolve(
        self,
        query: str,
        *,
        chat_history: Sequence[dict[str, str]] | None = None,
    ) -> Optional[AdapterResult]:
        """Resolve query using structured intent routing, then domain adapters."""
        intent = route_live_intent(query, chat_history=chat_history)
        if not is_structured_live_intent(intent):
            return None

        assert intent is not None
        handlers = {
            "fx": self._resolve_fx_intent,
            "commodity": self._resolve_commodity_intent,
            "stock": self._resolve_stock_intent,
            "weather_current": self._resolve_weather_current_intent,
            "weather_forecast": self._resolve_weather_forecast_intent,
            "news": self._resolve_news_intent,
            "game_score": self._resolve_game_score_intent,
            "nearby_places": self._resolve_nearby_places_intent,
        }
        handler = handlers.get(intent.domain)
        if handler is None:
            return None
        if intent.domain == "nearby_places":
            return await self._resolve_nearby_places_intent(
                intent,
                query=query,
                chat_history=chat_history,
            )
        return await handler(intent)

    async def _get_cache(self, key: str, domain: str) -> Optional[AdapterResult]:
        cached = await self._cache.get(key)
        if cached is not None:
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=cached.status, source=cached.source or "cache", cache_hit="true").inc()
        return cached

    async def _set_cache(self, key: str, result: AdapterResult) -> None:
        await self._cache.set(key, result, result.ttl_seconds)

    async def _resolve_fx_intent(self, intent: LiveIntent) -> AdapterResult:
        base = intent.slots["base"]
        quote = intent.slots["quote"]
        domain = "fx"
        cache_key = f"adapter:{domain}:{base}:{quote}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_fx_rate(base, quote)
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Frankfurter API",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 30),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message="Unable to fetch live FX rate",
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source="Frankfurter API",
            provider_timestamp=payload.get("date") or None,
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data=payload,
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_commodity_intent(self, intent: LiveIntent) -> AdapterResult:
        ticker = intent.slots["ticker"]
        label = intent.slots["label"]
        domain = "commodity"
        cache_key = f"adapter:{domain}:{ticker}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_commodity_price(ticker)
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Market Data",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 30),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to fetch market price for {ticker}",
                data={"ticker": ticker, "label": label},
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        payload["label"] = label
        source = payload.get("source", "Yahoo Finance")
        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source=source,
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data=payload,
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_stock_intent(self, intent: LiveIntent) -> AdapterResult:
        ticker = intent.slots["ticker"]
        domain = "stock"
        cache_key = f"adapter:{domain}:{ticker}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_stock_quote(ticker)
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Market Data",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 20),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to fetch stock quote for {ticker}",
                data={"ticker": ticker},
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        source = payload.get("source", "Yahoo Finance")
        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source=source,
            provider_timestamp=payload.get("market_time_utc") or None,
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data=payload,
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_weather_current_intent(self, intent: LiveIntent) -> AdapterResult:
        location = intent.slots["location"]
        domain = "weather_current"
        cache_key = f"adapter:{domain}:{location.lower()}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_weather(location)
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Open-Meteo",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 60),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to resolve live weather for location '{location}'",
                data={"location": location},
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source="Open-Meteo",
            provider_timestamp=payload.get("time") or None,
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data=payload,
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_weather_forecast_intent(self, intent: LiveIntent) -> AdapterResult:
        location = intent.slots["location"]
        days = int(intent.slots.get("days", 3))
        domain = "weather_forecast"
        cache_key = f"adapter:{domain}:{location.lower()}:{days}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_weather_forecast(location, days=days)
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Open-Meteo",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 120),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to resolve weather forecast for '{location}'",
                data={"location": location, "days": days},
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source="Open-Meteo",
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data=payload,
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_news_intent(self, intent: LiveIntent) -> AdapterResult:
        topic = intent.slots["topic"]
        domain = "news"
        cache_key = f"adapter:{domain}:{topic.lower()}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_news(topic, limit=5)
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Google News RSS",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 60),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to fetch latest headlines for '{topic}'",
                data={"topic": topic},
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        provider_timestamp = payload[0].get("published_at") if payload else None
        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source="Google News RSS",
            provider_timestamp=provider_timestamp,
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data={"topic": topic, "headlines": payload},
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_game_score_intent(self, intent: LiveIntent) -> AdapterResult:
        league = str(intent.slots.get("league") or "nba")
        team_query = str(intent.slots.get("team_query") or "")
        opponent_query = str(intent.slots.get("opponent_query") or "") or None
        domain = "game_score"
        cache_key = f"adapter:{domain}:{league}:{team_query.lower()}:{(opponent_query or '').lower()}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._sports.fetch_game_for_team(
            league,
            team_query,
            opponent_query=opponent_query,
        )
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="ESPN Scoreboard",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 30),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to find a live score for '{team_query}' in {league.upper()}",
                data={"league": league, "team_query": team_query},
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source=payload.get("source", "ESPN Scoreboard"),
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data=payload,
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_nearby_places_intent(
        self,
        intent: LiveIntent,
        *,
        query: str,
        chat_history: Sequence[dict[str, str]] | None = None,
    ) -> AdapterResult:
        from app.core.deps import get_llm_gateway
        from app.services.nearby_places_clarification import assess_nearby_places_readiness

        assessment = await assess_nearby_places_readiness(
            query,
            intent,
            chat_history=chat_history,
            settings=self._settings,
            llm_gateway=get_llm_gateway(),
            planner=StageModelConfig(
                provider=self._settings.llm_planner_provider,
                model=self._settings.llm_planner_model,
            ),
        )

        if not assessment.ready_to_search:
            error_code = (
                "LOCATION_REQUIRED"
                if bool(intent.slots.get("needs_location"))
                else "CLARIFICATION_REQUIRED"
            )
            return AdapterResult(
                domain="nearby_places",
                status="partial",
                verified=False,
                source="Personal AI",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=10,
                error_code=error_code,
                error_message=assessment.question or location_prompt_text(category=assessment.category),
                data={
                    "category": assessment.category,
                    "needs_location": error_code == "LOCATION_REQUIRED",
                },
                confidence=intent.confidence,
            )

        location = assessment.location.strip()
        category = assessment.category
        domain = "nearby_places"
        cache_key = f"adapter:{domain}:{location.lower()}:{category}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await fetch_nearby_places(location, category=category)
        latency = time.perf_counter() - started
        ttl = self._domain_ttl(domain)

        if not payload or not payload.get("places"):
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="OpenStreetMap",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=min(ttl, 30),
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Couldn't find {category.replace('_', ' ')} near '{location}'. Try a nearby city name.",
                data={"location": location, "category": category},
                confidence=intent.confidence,
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source="OpenStreetMap",
            fetched_at_utc=self._now_utc(),
            ttl_seconds=ttl,
            data=payload,
            confidence=intent.confidence,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result


    def render(self, result: AdapterResult) -> Tuple[str, str]:
        """Render normalized adapter result into readable chat text + fetched timestamp."""
        ts = result.fetched_at_utc
        source = result.source or "unknown"

        if result.status != "ok" or not result.verified:
            if result.error_code in {"LOCATION_REQUIRED", "CLARIFICATION_REQUIRED"}:
                return result.error_message or location_prompt_text(category="general"), ts
            detail = result.error_message or "The provider did not return verified data."
            msg = (
                f"I couldn't fetch verified live {result.domain.replace('_', ' ')} data.\n\n"
                f"{detail}\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        if result.domain == "fx":
            data = result.data
            base = data.get("base", "")
            quote = data.get("quote", "")
            rate = float(data.get("rate", 0.0))
            provider_date = data.get("date", "")
            msg = (
                f"**1 {base} = {rate:.4f} {quote}**\n\n"
                f"As of {provider_date}\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        if result.domain == "commodity":
            data = result.data
            label = data.get("label", data.get("ticker", "Asset"))
            price = float(data.get("price", 0.0))
            currency = data.get("currency", "")
            msg = (
                f"**{label}** — **{price:.2f} {currency}**\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        if result.domain == "stock":
            data = result.data
            change = data.get("change")
            change_pct = data.get("change_percent")
            change_text = "N/A"
            if change is not None and change_pct is not None:
                sign = "+" if float(change) >= 0 else ""
                change_text = f"{sign}{float(change):.2f} ({sign}{float(change_pct):.2f}%)"
            ticker = data.get("ticker", "")
            name = data.get("name", "")
            currency = data.get("currency", "")
            price = float(data.get("price", 0.0))
            details = [
                f"- Day change: {change_text}",
                f"- Previous close: {data.get('previous_close')} {currency}",
                f"- Exchange: {data.get('exchange', '')}",
            ]
            market_state = str(data.get("market_state") or "").strip()
            if market_state:
                details.append(f"- Market state: {market_state}")
            msg = (
                f"**{name} ({ticker})** — **{price:.2f} {currency}**\n\n"
                f"{chr(10).join(details)}\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        if result.domain == "weather_current":
            data = result.data
            location = data.get("location", "")
            condition = _weather_label(data.get("weather_code"))
            temp = data.get("temperature")
            temp_unit = data.get("temperature_unit", "°C")
            feels = data.get("feels_like")
            humidity = data.get("humidity")
            humidity_unit = data.get("humidity_unit", "%")
            precip = data.get("precipitation")
            precip_unit = data.get("precipitation_unit", "mm")
            wind = data.get("wind_speed")
            wind_unit = data.get("wind_speed_unit", "km/h")
            details = [
                f"Feels like {feels} {temp_unit}",
                f"Humidity {humidity}{humidity_unit}",
                f"Wind {wind} {wind_unit}",
                f"Rain {precip} {precip_unit}",
            ]
            msg = (
                f"**{location}** — **{condition}, {temp} {temp_unit}**\n\n"
                f"{' · '.join(details)}\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        if result.domain == "weather_forecast":
            data = result.data
            rows = data.get("days", [])
            location = data.get("location", "")
            temp_unit = data.get("temp_unit", "°C")
            precip_unit = data.get("precip_unit", "mm")
            wind_unit = data.get("wind_unit", "km/h")
            day_count = len(rows)
            day_lines: list[str] = []
            for row in rows:
                label = _format_day_label(str(row.get("date", "")))
                condition = _weather_label(row.get("code"))
                temps = _format_temp_range(row.get("temp_min"), row.get("temp_max"), temp_unit)
                parts = [condition]
                if temps:
                    parts.append(temps)
                precip = row.get("precip")
                if precip is not None and float(precip) > 0:
                    parts.append(f"{float(precip):.1f} {precip_unit} rain")
                wind = row.get("wind_max")
                if wind is not None:
                    parts.append(f"winds to {float(wind):.0f} {wind_unit}")
                day_lines.append(f"**{label}** — {' · '.join(parts)}")
            msg = (
                f"**{location}** — {day_count}-day forecast\n\n"
                f"{chr(10).join(day_lines)}\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        if result.domain == "news":
            data = result.data
            topic = data.get("topic", "news")
            headline_lines: list[str] = []
            for idx, item in enumerate(data.get("headlines", []), start=1):
                title = item.get("title", "Untitled")
                publisher = item.get("source", "")
                published = _format_news_date(item.get("published_at", ""))
                byline = f" — {publisher}" if publisher else ""
                if published:
                    byline += f" ({published})"
                headline_lines.append(f"{idx}. **{title}**{byline}")
            msg = (
                f"**Latest on {topic}**\n\n"
                f"{chr(10).join(headline_lines)}\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        if result.domain == "game_score":
            data = result.data
            away = data.get("away_team", "Away")
            home = data.get("home_team", "Home")
            away_score = data.get("away_score", 0)
            home_score = data.get("home_score", 0)
            status = data.get("status", "")
            league = data.get("league", "")
            live_tag = " · LIVE" if data.get("is_live") else ""
            msg = (
                f"**{away} {away_score} – {home} {home_score}**{live_tag}\n\n"
                f"{league} · {status}\n\n"
                f"{_meta_footer(source, ts)}"
            )
            return msg, ts

        msg = _meta_footer(source, ts)
        return msg, ts

    async def refresh_block(self, subscription_key: str) -> Optional[ContentBlock]:
        """Refresh a live card by subscription key (sports event or live stock ticker)."""
        key = subscription_key.strip()
        if not key:
            return None

        parts = key.split(":", 2)
        kind = parts[0].lower()

        if kind == "sports":
            rest = key.split(":", 1)[1] if ":" in key else ""
            if not rest or ":" not in rest:
                return None
            league, event_id = rest.rsplit(":", 1)
            payload = await self._sports.fetch_event_by_id(league, event_id)
            if not payload:
                return None
            result = AdapterResult(
                domain="game_score",
                status="ok",
                verified=True,
                source=payload.get("source", "ESPN Scoreboard"),
                fetched_at_utc=self._now_utc(),
                ttl_seconds=self._domain_ttl("game_score"),
                data=payload,
            )
            blocks = self.to_blocks(result)
            return blocks[0] if blocks else None

        if kind == "stock" and len(parts) == 2:
            ticker = parts[1].upper()
            payload = await self._web.get_live_stock_quote(ticker)
            if not payload:
                return None
            result = AdapterResult(
                domain="stock",
                status="ok",
                verified=True,
                source=payload.get("source", "Market Data"),
                provider_timestamp=payload.get("market_time_utc") or None,
                fetched_at_utc=self._now_utc(),
                ttl_seconds=self._domain_ttl("stock"),
                data=payload,
            )
            blocks = self.to_blocks(result)
            return blocks[0] if blocks else None

        if kind == "crypto" and len(parts) == 2:
            from app.services.live_providers import fetch_crypto_price

            symbol = parts[1]
            payload = await fetch_crypto_price(symbol)
            if not payload:
                return None
            blocks = self.to_blocks(
                AdapterResult(
                    domain="commodity",
                    status="ok",
                    verified=True,
                    source=payload.get("source", "CoinGecko"),
                    fetched_at_utc=self._now_utc(),
                    ttl_seconds=20,
                    data={
                        "ticker": f"{symbol}-USD",
                        "label": symbol,
                        "price": payload.get("price"),
                        "currency": "USD",
                    },
                )
            )
            if blocks:
                return blocks[0]
            return ContentBlock(type="crypto", subscription_key=f"crypto:{symbol}", data=payload)

        return None


__all__ = ["LiveDataManager"]
