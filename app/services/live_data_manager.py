from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Optional, Tuple

from prometheus_client import Counter, Histogram

from app.core.config import Settings
from app.schemas.adapter import AdapterResult
from app.services.adapter_cache import AdapterCache
from app.services.web_search import (
    WebSearchService,
    detect_commodity_query,
    detect_stock_query,
    extract_currency_pair,
    extract_forecast_days,
    extract_news_topic,
    extract_weather_location,
    is_news_query,
    is_weather_query,
    should_prioritize_fresh_web_data,
)

logger = logging.getLogger(__name__)

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

    def is_live_intent_query(self, query: str) -> bool:
        text = query.strip()
        if not text:
            return False
        return (
            extract_currency_pair(text) is not None
            or detect_commodity_query(text) is not None
            or detect_stock_query(text) is not None
            or is_weather_query(text)
            or is_news_query(text)
            or should_prioritize_fresh_web_data(text)
        )

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
        """Resolve query against deterministic adapters in priority order."""
        resolvers = [
            self._resolve_fx,
            self._resolve_commodity,
            self._resolve_stock,
            self._resolve_weather_forecast,
            self._resolve_weather_current,
            self._resolve_news,
        ]

        for resolver in resolvers:
            result = await resolver(query)
            if result is not None:
                return result
        return None

    async def _get_cache(self, key: str, domain: str) -> Optional[AdapterResult]:
        cached = await self._cache.get(key)
        if cached is not None:
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=cached.status, source=cached.source or "cache", cache_hit="true").inc()
        return cached

    async def _set_cache(self, key: str, result: AdapterResult) -> None:
        await self._cache.set(key, result, result.ttl_seconds)

    async def _resolve_fx(self, query: str) -> Optional[AdapterResult]:
        pair = extract_currency_pair(query)
        if not pair:
            return None

        domain = "fx"
        cache_key = f"adapter:{domain}:{pair[0]}:{pair[1]}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_fx_rate(pair[0], pair[1])
        latency = time.perf_counter() - started

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Frankfurter API",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=30,
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message="Unable to fetch live FX rate",
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
            ttl_seconds=60,
            data=payload,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_commodity(self, query: str) -> Optional[AdapterResult]:
        match = detect_commodity_query(query)
        if not match:
            return None

        ticker, label = match
        domain = "commodity"
        cache_key = f"adapter:{domain}:{ticker}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_commodity_price(ticker)
        latency = time.perf_counter() - started

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Yahoo Finance",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=30,
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to fetch market price for {ticker}",
                data={"ticker": ticker, "label": label},
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        payload["label"] = label
        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source="Yahoo Finance",
            fetched_at_utc=self._now_utc(),
            ttl_seconds=30,
            data=payload,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_stock(self, query: str) -> Optional[AdapterResult]:
        ticker = detect_stock_query(query)
        if not ticker:
            return None

        domain = "stock"
        cache_key = f"adapter:{domain}:{ticker}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_stock_quote(ticker)
        latency = time.perf_counter() - started

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Yahoo Finance",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=20,
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to fetch stock quote for {ticker}",
                data={"ticker": ticker},
            )
            ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
            ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
            return result

        result = AdapterResult(
            domain=domain,
            status="ok",
            verified=True,
            source="Yahoo Finance",
            provider_timestamp=payload.get("market_time_utc") or None,
            fetched_at_utc=self._now_utc(),
            ttl_seconds=30,
            data=payload,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_weather_current(self, query: str) -> Optional[AdapterResult]:
        location = extract_weather_location(query)
        if not location:
            return None

        lower = query.lower()
        if any(term in lower for term in ["forecast", "tomorrow", "week", "weekly", "next", "day"]):
            return None

        domain = "weather_current"
        cache_key = f"adapter:{domain}:{location.lower()}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_weather(location)
        latency = time.perf_counter() - started

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Open-Meteo",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=60,
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to resolve live weather for location '{location}'",
                data={"location": location},
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
            ttl_seconds=300,
            data=payload,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_weather_forecast(self, query: str) -> Optional[AdapterResult]:
        lower = query.lower()
        if not any(term in lower for term in ["forecast", "tomorrow", "week", "weekly", "next", "day"]):
            return None

        location = extract_weather_location(query)
        if not location:
            return None
        days = extract_forecast_days(query)

        domain = "weather_forecast"
        cache_key = f"adapter:{domain}:{location.lower()}:{days}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_weather_forecast(location, days=days)
        latency = time.perf_counter() - started

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Open-Meteo",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=120,
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to resolve weather forecast for '{location}'",
                data={"location": location, "days": days},
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
            ttl_seconds=900,
            data=payload,
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    async def _resolve_news(self, query: str) -> Optional[AdapterResult]:
        if not is_news_query(query):
            return None

        topic = extract_news_topic(query)
        domain = "news"
        cache_key = f"adapter:{domain}:{topic.lower()}"
        cached = await self._get_cache(cache_key, domain)
        if cached:
            return cached

        started = time.perf_counter()
        payload = await self._web.get_live_news(topic, limit=5)
        latency = time.perf_counter() - started

        if not payload:
            result = AdapterResult(
                domain=domain,
                status="error",
                verified=False,
                source="Google News RSS",
                fetched_at_utc=self._now_utc(),
                ttl_seconds=60,
                error_code="LIVE_DATA_NOT_VERIFIED",
                error_message=f"Unable to fetch latest headlines for '{topic}'",
                data={"topic": topic},
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
            ttl_seconds=180,
            data={"topic": topic, "headlines": payload},
        )
        ADAPTER_REQUESTS_TOTAL.labels(domain=domain, status=result.status, source=result.source, cache_hit="false").inc()
        ADAPTER_LATENCY_SECONDS.labels(domain=domain, source=result.source).observe(latency)
        await self._set_cache(cache_key, result)
        return result

    def render(self, result: AdapterResult) -> Tuple[str, str]:
        """Render normalized adapter result into terminal response + fetched timestamp."""
        ts = result.fetched_at_utc

        if result.status != "ok" or not result.verified:
            msg = (
                f"LIVE {result.domain.upper()} DATA REQUEST RECEIVED.\n"
                "ERROR 404: LIVE DATA NOT VERIFIED\n"
                f"- Source: {result.source or 'UNKNOWN'}\n"
                f"- Fetched: {ts}"
            )
            return msg, ts

        if result.domain == "fx":
            data = result.data
            msg = (
                "LIVE CURRENCY DATA RETRIEVED. OUTPUT VERIFIED AGAINST REAL-TIME FX FEED.\n"
                "Verified live FX rate:\n"
                f"- 1 {data.get('base')} = {float(data.get('rate', 0.0)):.6f} {data.get('quote')}\n"
                f"- Provider date: {data.get('date', '')}\n"
                f"- Fetched: {ts}\n"
                f"- Source: {result.source}"
            )
            return msg, ts

        if result.domain == "commodity":
            data = result.data
            msg = (
                "LIVE MARKET DATA RETRIEVED. OUTPUT VERIFIED AGAINST REAL-TIME FEED.\n"
                "Verified live market price:\n"
                f"- {data.get('label', data.get('ticker', 'ASSET'))}: {float(data.get('price', 0.0)):.2f} {data.get('currency', '')}\n"
                f"- Fetched: {ts}\n"
                f"- Source: {result.source}"
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
            msg = (
                "LIVE STOCK DATA RETRIEVED. OUTPUT VERIFIED AGAINST REAL-TIME MARKET FEED.\n"
                "Verified live stock quote:\n"
                f"- Symbol: {data.get('ticker', '')}\n"
                f"- Name: {data.get('name', '')}\n"
                f"- Price: {float(data.get('price', 0.0)):.2f} {data.get('currency', '')}\n"
                f"- Day change: {change_text}\n"
                f"- Previous close: {data.get('previous_close')} {data.get('currency', '')}\n"
                f"- Exchange: {data.get('exchange', '')}\n"
                f"- Market state: {data.get('market_state', '')}\n"
                f"- Market time (UTC): {data.get('market_time_utc', '')}\n"
                f"- Fetched: {ts}\n"
                f"- Source: {result.source}"
            )
            return msg, ts

        if result.domain == "weather_current":
            data = result.data
            code = data.get("weather_code")
            msg = (
                "LIVE WEATHER DATA RETRIEVED. OUTPUT VERIFIED AGAINST REAL-TIME METEOROLOGICAL FEED.\n"
                "Verified current weather:\n"
                f"- Location: {data.get('location', '')}\n"
                f"- Observation time: {data.get('time', '')}\n"
                f"- Condition code: {code}\n"
                f"- Temperature: {data.get('temperature')} {data.get('temperature_unit', '')}\n"
                f"- Feels like: {data.get('feels_like')} {data.get('temperature_unit', '')}\n"
                f"- Humidity: {data.get('humidity')}{data.get('humidity_unit', '')}\n"
                f"- Precipitation: {data.get('precipitation')} {data.get('precipitation_unit', '')}\n"
                f"- Wind: {data.get('wind_speed')} {data.get('wind_speed_unit', '')}\n"
                f"- Fetched: {ts}\n"
                f"- Source: {result.source}"
            )
            return msg, ts

        if result.domain == "weather_forecast":
            data = result.data
            rows = data.get("days", [])
            lines = [
                "LIVE WEATHER FORECAST DATA RETRIEVED. OUTPUT VERIFIED AGAINST REAL-TIME METEOROLOGICAL FEED.",
                "Verified weather forecast:",
                f"- Location: {data.get('location', '')}",
                f"- Horizon: {len(rows)} day(s)",
            ]
            for row in rows:
                lines.append(
                    (
                        f"- {row.get('date')}: code={row.get('code')}, "
                        f"max={row.get('temp_max')} {data.get('temp_unit', '')}, "
                        f"min={row.get('temp_min')} {data.get('temp_unit', '')}, "
                        f"precip={row.get('precip')} {data.get('precip_unit', '')}, "
                        f"wind_max={row.get('wind_max')} {data.get('wind_unit', '')}"
                    )
                )
            lines.append(f"- Fetched: {ts}")
            lines.append(f"- Source: {result.source}")
            return "\n".join(lines), ts

        if result.domain == "news":
            data = result.data
            lines = [
                "LIVE NEWS DATA RETRIEVED. OUTPUT VERIFIED AGAINST CURRENT NEWS FEED.",
                "Verified latest news headlines:",
                f"- Topic: {data.get('topic', '')}",
            ]
            for idx, item in enumerate(data.get("headlines", []), start=1):
                lines.append(
                    f"- #{idx}: {item.get('title', '')} | source={item.get('source', '')} | published={item.get('published_at', '')}"
                )
                if item.get("link"):
                    lines.append(f"  link={item.get('link')}")
            lines.append(f"- Fetched: {ts}")
            lines.append(f"- Source: {result.source}")
            return "\n".join(lines), ts

        msg = (
            f"LIVE {result.domain.upper()} DATA RETRIEVED.\n"
            f"- Source: {result.source}\n"
            f"- Fetched: {ts}"
        )
        return msg, ts


__all__ = ["LiveDataManager"]
