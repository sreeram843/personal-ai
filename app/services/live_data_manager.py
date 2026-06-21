from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Optional, Tuple

from prometheus_client import Counter, Histogram

from app.core.config import Settings
from app.schemas.adapter import AdapterResult
from app.schemas.live_intent import LiveDataProvenance, LiveIntent
from app.services.adapter_cache import AdapterCache
from app.services.live_intent_router import is_structured_live_intent, route_live_intent
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

    def __init__(self, web_search: WebSearchService, cache: AdapterCache, settings: Settings) -> None:
        self._web = web_search
        self._cache = cache
        self._settings = settings

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

    async def resolve(self, query: str) -> Optional[AdapterResult]:
        """Resolve query using structured intent routing, then domain adapters."""
        intent = route_live_intent(query)
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
        }
        handler = handlers.get(intent.domain)
        if handler is None:
            return None
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


    def render(self, result: AdapterResult) -> Tuple[str, str]:
        """Render normalized adapter result into readable chat text + fetched timestamp."""
        ts = result.fetched_at_utc
        source = result.source or "unknown"

        if result.status != "ok" or not result.verified:
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

        msg = _meta_footer(source, ts)
        return msg, ts


__all__ = ["LiveDataManager"]
