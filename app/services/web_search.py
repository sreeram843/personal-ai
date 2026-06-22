from __future__ import annotations

"""Web search service using DuckDuckGo API."""

import asyncio
from datetime import datetime, timezone
import logging
import re
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import httpx
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# ISO-4217 alphabetic codes used to reject false currency pairs from plain English
# (e.g. "our" / "nda" were previously treated as OUR/NDA).
_KNOWN_CCY_ALPHA3: frozenset[str] = frozenset(
    "AED ARS AUD BGN BHD BRL CAD CHF CLP CNY COP CZK DKK EGP ETB EUR GBP GHS HKD HUF ILS "
    "INR ISK JOD JPY KRW LKR MXN MYR NGN NOK NPR NZD PHP PLN RON RUB SEK SGD THB TRY TWD UAH "
    "UGX USD UYU UZS VND XAF XOF ZAR".split()
)


def _fmt_utc() -> str:
    """Return a human-readable UTC timestamp: 'YYYY-MM-DD HH:MM:SS UTC'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class WebSearchService:
    """Search the web using DuckDuckGo."""

    def __init__(
        self,
        max_results: int = 5,
        timeout: int = 10,
        *,
        geocoder=None,
        market_data=None,
    ):
        """Initialize web search service."""
        self.max_results = max_results
        self.timeout = timeout
        self._geocoder = geocoder
        self._market_data = market_data

    async def search(self, query: str) -> list[dict]:
        """Search DuckDuckGo for query results.
        
        Args:
            query: Search query string
            
        Returns:
            List of search results with 'title', 'body', 'href' keys
        """
        try:
            # Run DDGS search in threadpool to avoid blocking
            results = await asyncio.to_thread(
                self._search_sync,
                query
            )
            return results
        except Exception as exc:
            logger.error(f"Web search error for query '{query}': {exc}")
            return []

    async def get_live_fx_rate(self, base_currency: str, quote_currency: str) -> dict | None:
        """Fetch live FX rate from Frankfurter API.

        Returns a dict with base, quote, rate, and date when available.
        """
        base = base_currency.upper().strip()
        quote = quote_currency.upper().strip()
        url = f"https://api.frankfurter.dev/v1/latest?from={base}&to={quote}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning(f"FX rate fetch failed for {base}/{quote}: {exc}")
            return None

        rates = payload.get("rates", {})
        rate = rates.get(quote)
        if rate is None:
            return None

        return {
            "base": payload.get("base", base),
            "quote": quote,
            "rate": float(rate),
            "date": payload.get("date", ""),
            "source": "Frankfurter API",
        }

    async def build_live_fx_context(self, user_query: str) -> str:
        """Build deterministic live FX context for conversion/rate queries."""
        pair = extract_currency_pair(user_query)
        if not pair:
            return ""

        fx = await self.get_live_fx_rate(pair[0], pair[1])
        if not fx:
            return ""

        fetched_at = _fmt_utc()

        return (
            "Verified live FX rate:\n"
            f"- 1 {fx['base']} = {fx['rate']:.6f} {fx['quote']}\n"
            f"- Provider date: {fx['date']}\n"
            f"- Fetched: {fetched_at}\n"
            f"- Source: {fx['source']}"
        )

    async def get_live_commodity_price(self, ticker: str) -> dict | None:
        """Fetch live commodity/crypto price via configured market data provider."""
        if self._market_data is not None:
            return await self._market_data.get_commodity_price(ticker)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; personal-ai-bot/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(url, params={"interval": "1m", "range": "1d"})
                response.raise_for_status()
                data = response.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            if price is None:
                return None
            return {
                "ticker": ticker,
                "price": float(price),
                "currency": meta.get("currency", "USD"),
                "source": "Yahoo Finance",
            }
        except Exception as exc:
            logger.warning(f"Commodity price fetch failed for {ticker}: {exc}")
            return None

    async def get_live_stock_quote(self, ticker: str) -> dict | None:
        """Fetch enriched live stock/ETF quote via configured market data provider."""
        if self._market_data is not None:
            return await self._market_data.get_stock_quote(ticker)
        symbol = ticker.upper().strip()
        if not symbol:
            return None

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; personal-ai-bot/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
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
                market_time_utc = datetime.fromtimestamp(int(market_time), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
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
            logger.warning(f"Stock quote fetch failed for {symbol}: {exc}")
            return None

    async def build_live_commodity_context(self, user_query: str) -> str:
        """Build deterministic live commodity/crypto price context if query matches."""
        match = detect_commodity_query(user_query)
        if not match:
            return ""
        ticker, label = match
        data = await self.get_live_commodity_price(ticker)
        if not data:
            return ""
        fetched_at = _fmt_utc()
        return (
            f"Verified live market price:\n"
            f"- {label}: {data['price']:.2f} {data['currency']}\n"
            f"- Fetched: {fetched_at}\n"
            f"- Source: {data['source']}"
        )

    async def build_live_stock_context(self, user_query: str) -> str:
        """Build deterministic live stock price context if query contains a ticker."""
        # Don't double-handle commodities/crypto already covered by build_live_commodity_context
        if detect_commodity_query(user_query):
            return ""
        ticker = detect_stock_query(user_query)
        if not ticker:
            return ""
        data = await self.get_live_stock_quote(ticker)
        if not data:
            return ""
        fetched_at = _fmt_utc()
        change_text = "N/A"
        if data.get("change") is not None and data.get("change_percent") is not None:
            sign = "+" if float(data["change"]) >= 0 else ""
            change_text = f"{sign}{float(data['change']):.2f} ({sign}{float(data['change_percent']):.2f}%)"

        return (
            f"Verified live stock quote:\n"
            f"- Symbol: {data['ticker']}\n"
            f"- Name: {data['name']}\n"
            f"- Price: {data['price']:.2f} {data['currency']}\n"
            f"- Day change: {change_text}\n"
            f"- Previous close: {data['previous_close']} {data['currency']}\n"
            f"- Exchange: {data['exchange']}\n"
            f"- Market state: {data['market_state']}\n"
            f"- Market time (UTC): {data['market_time_utc']}\n"
            f"- Fetched: {fetched_at}\n"
            f"- Source: {data['source']} (real-time market data)"
        )

    async def _geocode_location(self, location: str) -> dict | None:
        """Resolve place name to geocoding payload via Open-Meteo."""
        if self._geocoder is not None:
            return await self._geocoder.resolve(location)
        place = location.strip()
        if not place:
            return None

        # Try a few normalized variants because state abbreviations like
        # "Overland Park, KS" may not resolve while "Overland Park" does.
        candidates = [place]
        no_state_abbrev = re.sub(r",\s*[A-Z]{2}\b", "", place)
        if no_state_abbrev and no_state_abbrev != place:
            candidates.append(no_state_abbrev.strip())
        if "," in place:
            first_segment = place.split(",", 1)[0].strip()
            if first_segment and first_segment not in candidates:
                candidates.append(first_segment)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for candidate in candidates:
                    geocode_resp = await client.get(
                        "https://geocoding-api.open-meteo.com/v1/search",
                        params={"name": candidate, "count": 1, "language": "en", "format": "json"},
                    )
                    geocode_resp.raise_for_status()
                    geo_payload = geocode_resp.json()
                    results = geo_payload.get("results") or []
                    if results:
                        return results[0]
        except Exception as exc:
            logger.warning(f"Geocode failed for '{place}': {exc}")
            return None

        return None

    async def get_live_weather(self, location: str) -> dict | None:
        """Fetch current weather for a location using Open-Meteo (no API key)."""
        best = await self._geocode_location(location)
        if not best:
            return None

        lat = best.get("latitude")
        lon = best.get("longitude")
        if lat is None or lon is None:
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                weather_resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                        "timezone": "auto",
                    },
                )
                weather_resp.raise_for_status()
                weather_payload = weather_resp.json()
        except Exception as exc:
            logger.warning(f"Weather fetch failed for '{location}': {exc}")
            return None

        current = weather_payload.get("current") or {}
        units = weather_payload.get("current_units") or {}

        label_parts = [best.get("name", location)]
        if best.get("admin1"):
            label_parts.append(best["admin1"])
        if best.get("country"):
            label_parts.append(best["country"])

        return {
            "location": ", ".join(label_parts),
            "time": current.get("time", ""),
            "temperature": current.get("temperature_2m"),
            "temperature_unit": units.get("temperature_2m", "C"),
            "feels_like": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "humidity_unit": units.get("relative_humidity_2m", "%"),
            "precipitation": current.get("precipitation"),
            "precipitation_unit": units.get("precipitation", "mm"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_speed_unit": units.get("wind_speed_10m", "km/h"),
            "weather_code": current.get("weather_code"),
            "source": "Open-Meteo",
        }

    async def get_live_weather_forecast(self, location: str, days: int = 3) -> dict | None:
        """Fetch short-range weather forecast for a location via Open-Meteo."""
        best = await self._geocode_location(location)
        if not best:
            return None

        lat = best.get("latitude")
        lon = best.get("longitude")
        if lat is None or lon is None:
            return None

        forecast_days = max(1, min(days, 7))
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                forecast_resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                        "forecast_days": forecast_days,
                        "timezone": "auto",
                    },
                )
                forecast_resp.raise_for_status()
                payload = forecast_resp.json()
        except Exception as exc:
            logger.warning(f"Weather forecast fetch failed for '{location}': {exc}")
            return None

        daily = payload.get("daily") or {}
        units = payload.get("daily_units") or {}
        times = daily.get("time") or []
        max_t = daily.get("temperature_2m_max") or []
        min_t = daily.get("temperature_2m_min") or []
        precip = daily.get("precipitation_sum") or []
        wind = daily.get("wind_speed_10m_max") or []
        codes = daily.get("weather_code") or []

        rows: list[dict] = []
        for i, day in enumerate(times):
            rows.append(
                {
                    "date": day,
                    "code": codes[i] if i < len(codes) else None,
                    "temp_max": max_t[i] if i < len(max_t) else None,
                    "temp_min": min_t[i] if i < len(min_t) else None,
                    "precip": precip[i] if i < len(precip) else None,
                    "wind_max": wind[i] if i < len(wind) else None,
                }
            )

        label_parts = [best.get("name", location)]
        if best.get("admin1"):
            label_parts.append(best["admin1"])
        if best.get("country"):
            label_parts.append(best["country"])

        return {
            "location": ", ".join(label_parts),
            "days": rows,
            "temp_unit": units.get("temperature_2m_max", "C"),
            "precip_unit": units.get("precipitation_sum", "mm"),
            "wind_unit": units.get("wind_speed_10m_max", "km/h"),
            "source": "Open-Meteo",
        }

    async def build_live_weather_context(self, user_query: str) -> str:
        """Build deterministic live weather context if a weather query is detected."""
        location = extract_weather_location(user_query)
        if not location:
            return ""

        weather = await self.get_live_weather(location)
        if not weather:
            return ""

        fetched_at = _fmt_utc()
        code = weather.get("weather_code")
        code_label = WEATHER_CODE_LABELS.get(code, "Unknown condition")
        location = weather["location"]
        temp = weather["temperature"]
        temp_unit = weather["temperature_unit"]
        feels = weather["feels_like"]
        humidity = weather["humidity"]
        humidity_unit = weather["humidity_unit"]
        precip = weather["precipitation"]
        precip_unit = weather["precipitation_unit"]
        wind = weather["wind_speed"]
        wind_unit = weather["wind_speed_unit"]

        return (
            f"**{location}** — **{code_label}, {temp} {temp_unit}**\n\n"
            f"Feels like {feels} {temp_unit} · Humidity {humidity}{humidity_unit} · "
            f"Wind {wind} {wind_unit} · Rain {precip} {precip_unit}\n\n"
            f"Source: {weather['source']} · Fetched: {fetched_at}"
        )

    async def build_weather_forecast_context(self, user_query: str) -> str:
        """Build deterministic weather forecast context for forecast-style queries."""
        lower = user_query.lower()
        if not any(term in lower for term in ["forecast", "tomorrow", "week", "weekly", "next", "day"]):
            return ""

        location = extract_weather_location(user_query)
        if not location:
            return ""

        days = extract_forecast_days(user_query)
        forecast = await self.get_live_weather_forecast(location, days=days)
        if not forecast:
            return ""

        fetched_at = _fmt_utc()
        location = forecast["location"]
        temp_unit = forecast["temp_unit"]
        precip_unit = forecast["precip_unit"]
        wind_unit = forecast["wind_unit"]
        day_lines: list[str] = []
        for row in forecast["days"]:
            code = row.get("code")
            code_label = WEATHER_CODE_LABELS.get(code, "Unknown condition")
            date_str = str(row.get("date", ""))
            try:
                day_label = datetime.strptime(date_str[:10], "%Y-%m-%d").strftime("%a, %b %d").replace(" 0", " ")
            except ValueError:
                day_label = date_str
            min_t = row.get("temp_min")
            max_t = row.get("temp_max")
            if min_t is not None and max_t is not None:
                temps = f"{float(min_t):.0f}–{float(max_t):.0f} {temp_unit}"
            else:
                temps = ""
            parts = [code_label]
            if temps:
                parts.append(temps)
            precip = row.get("precip")
            if precip is not None and float(precip) > 0:
                parts.append(f"{float(precip):.1f} {precip_unit} rain")
            wind = row.get("wind_max")
            if wind is not None:
                parts.append(f"winds to {float(wind):.0f} {wind_unit}")
            day_lines.append(f"**{day_label}** — {' · '.join(parts)}")

        return (
            f"**{location}** — {len(forecast['days'])}-day forecast\n\n"
            f"{chr(10).join(day_lines)}\n\n"
            f"Source: {forecast['source']} · Fetched: {fetched_at}"
        )

    async def get_live_news(self, topic: str, limit: int = 5) -> list[dict]:
        """Fetch latest headlines from Google News RSS (no API key)."""
        query = quote_plus(topic.strip() or "latest news")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_text = response.text
        except Exception as exc:
            logger.warning(f"News fetch failed for topic '{topic}': {exc}")
            return []

        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        items = root.findall("./channel/item")
        results: list[dict] = []
        for item in items[: max(1, min(limit, 10))]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            source_elem = item.find("source")
            source = ""
            if source_elem is not None:
                source = (source_elem.text or "").strip()

            if title:
                results.append(
                    {
                        "title": title,
                        "link": link,
                        "published_at": pub_date,
                        "source": source,
                        "fetched_at": _fmt_utc(),
                    }
                )

        return results

    async def build_live_news_context(self, user_query: str) -> str:
        """Build deterministic live news context for latest news queries."""
        if not is_news_query(user_query):
            return ""

        topic = extract_news_topic(user_query)
        headlines = await self.get_live_news(topic, limit=5)
        if not headlines:
            return ""

        lines = [
            "Verified latest news headlines:",
            f"- Topic: {topic}",
        ]
        for idx, item in enumerate(headlines, start=1):
            lines.append(
                f"- #{idx}: {item['title']} | source={item['source']} | published={item['published_at']}"
            )
            if item.get("link"):
                lines.append(f"  link={item['link']}")

        lines.append(f"- Fetched: {_fmt_utc()}")
        lines.append("- Source: Google News RSS")
        return "\n".join(lines)

    async def search_with_page_excerpts(self, query: str) -> list[dict]:
        """Search and enrich top web results with page excerpts for fresher context."""
        results = await self.search(query)
        if not results:
            return []

        # Fetch a small subset of pages to avoid latency spikes.
        top = results[:3]
        excerpts = await asyncio.gather(
            *[self._fetch_page_excerpt(item.get("href", "")) for item in top],
            return_exceptions=True,
        )

        enriched: list[dict] = []
        for result, excerpt in zip(top, excerpts):
            if isinstance(excerpt, Exception):
                excerpt_text = ""
            else:
                excerpt_text = excerpt

            enriched.append(
                {
                    "title": result.get("title", ""),
                    "body": result.get("body", ""),
                    "href": result.get("href", ""),
                    "excerpt": excerpt_text,
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Keep any additional search-only results (without fetched excerpt).
        for result in results[3:]:
            enriched.append(
                {
                    "title": result.get("title", ""),
                    "body": result.get("body", ""),
                    "href": result.get("href", ""),
                    "excerpt": "",
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )

        return enriched

    def _search_sync(self, query: str) -> list[dict]:
        """Synchronous DuckDuckGo search (runs in threadpool)."""
        try:
            with DDGS(timeout=self.timeout) as ddgs:
                results = list(
                    ddgs.text(
                        keywords=query,
                        max_results=self.max_results,
                        backend="lite",  # Use lite backend for faster results
                    )
                )
            return results
        except Exception as exc:
            logger.warning(f"DuckDuckGo search failed: {exc}")
            return []

    async def _fetch_page_excerpt(self, url: str) -> str:
        """Fetch and extract a short plain-text excerpt from a webpage."""
        if not url:
            return ""

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except Exception:
            return ""

        # Lightweight HTML-to-text extraction without extra dependencies.
        no_scripts = re.sub(r"<script[\\s\\S]*?</script>", " ", html, flags=re.IGNORECASE)
        no_styles = re.sub(r"<style[\\s\\S]*?</style>", " ", no_scripts, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", no_styles)
        text = re.sub(r"\\s+", " ", text).strip()
        if not text:
            return ""

        return text[:700]

    @staticmethod
    def format_results_for_context(results: list[dict]) -> str:
        """Format search results into context block for LLM.
        
        Args:
            results: List of search result dicts
            
        Returns:
            Formatted context string
        """
        if not results:
            return ""

        context_lines = ["Web search results:"]
        for idx, result in enumerate(results, start=1):
            title = result.get("title", "")
            body = result.get("body", "")
            href = result.get("href", "")
            excerpt = result.get("excerpt", "")
            fetched_at_utc = result.get("fetched_at_utc", "")
            context_lines.append(f"\n[Web Result {idx}] {title}")
            if href:
                context_lines.append(f"URL: {href}")
            if fetched_at_utc:
                context_lines.append(f"Fetched at UTC: {fetched_at_utc}")
            if body:
                # Truncate long body text
                truncated_body = body[:300] + "..." if len(body) > 300 else body
                context_lines.append(truncated_body)
            if excerpt:
                context_lines.append(f"Page excerpt: {excerpt}")

        return "\n".join(context_lines)


def should_use_web_search(response_text: str) -> bool:
    """Detect if response lacks confidence and web search is warranted.
    
    Args:
        response_text: Model's response text
    Returns:
        True if web search is recommended
    """
    uncertainty_indicators = [
        "i don't know",
        "i'm not sure",
        "i cannot",
        "unable to",
        "not available",
        "may not be accurate",
        "unknown",
        "unclear",
        "uncertain",
        "not certain",
        "insufficient information",
        "based on my training",
        "as of my knowledge",
    ]

    response_lower = response_text.lower()
    matches = sum(1 for indicator in uncertainty_indicators if indicator in response_lower)

    # If multiple uncertainty indicators or lack of confidence, suggest web search
    return matches >= 2 or (matches >= 1 and len(response_text) < 200)


def should_prioritize_fresh_web_data(user_query: str) -> bool:
    """Detect queries that usually need fresh internet data.

    Currency pairs are always treated as live. ``value``/``version`` are removed from
    loose substring matches (noisy for general questions). "current" is only counted
    when it is probably not a path/UI reference (e.g. not "current directory").
    """
    if extract_currency_pair(user_query) is not None:
        return True
    text = user_query.lower()

    freshness_terms = [
        "latest",
        "fresh",
        "today",
        "now",
        "recent",
        "newest",
        "update",
        "news",
        "price",
        "rate",
        "stock",
        "market",
        "release",
        "weather",
        "forecast",
        "headline",
        "headlines",
        "tomorrow",
        "weekly",
        "score",
        "election",
        "convert",
        "conversion",
        "exchange",
        "fx",
        "forex",
        "yesterday",
        "last week",
        "last month",
        "this week",
        "as of",
        "breaking",
    ]
    if any(term in text for term in freshness_terms):
        return True
    if re.search(r"\bcurrent\b", text) and "current directory" not in text and "current folder" not in text:
        return True
    if re.search(r"\b(versions?|v\d+\.\d+)\b", text):
        return True
    return False


def extract_currency_pair(user_query: str) -> tuple[str, str] | None:
    """Extract currency pair from user query.

    Supports patterns like:
    - "usd to inr"
    - "USD/INR"
    - "convert dollars to rupees"
    """
    text = user_query.lower()

    alias_to_code = {
        "usd": "USD",
        "dollar": "USD",
        "dollars": "USD",
        "inr": "INR",
        "rupee": "INR",
        "rupees": "INR",
        "eur": "EUR",
        "euro": "EUR",
        "gbp": "GBP",
        "pound": "GBP",
        "pounds": "GBP",
        "jpy": "JPY",
        "yen": "JPY",
        "aed": "AED",
        "dirham": "AED",
        "cad": "CAD",
        "aud": "AUD",
        "chf": "CHF",
        "cny": "CNY",
    }

    tokens = re.findall(r"[a-zA-Z]{3,}", text)
    codes: list[str] = []
    for token in tokens:
        mapped = alias_to_code.get(token)
        if mapped:
            codes.append(mapped)
        elif len(token) == 3 and token.isalpha() and token.upper() in _KNOWN_CCY_ALPHA3:
            codes.append(token.upper())

    slash_match = re.search(r"\b([a-zA-Z]{3})\s*/\s*([a-zA-Z]{3})\b", text)
    if slash_match:
        return slash_match.group(1).upper(), slash_match.group(2).upper()

    to_match = re.search(r"\b([a-zA-Z]{3,})\b\s+to\s+\b([a-zA-Z]{3,})\b", text)
    if to_match:
        left = alias_to_code.get(to_match.group(1), to_match.group(1).upper())
        right = alias_to_code.get(to_match.group(2), to_match.group(2).upper())
        if len(left) == 3 and len(right) == 3:
            return left, right

    unique_codes: list[str] = []
    for code in codes:
        if code not in unique_codes:
            unique_codes.append(code)
    if len(unique_codes) >= 2:
        return unique_codes[0], unique_codes[1]

    return None


# ---------------------------------------------------------------------------
# Commodity price helpers
# ---------------------------------------------------------------------------

_COMMODITY_MAP: list[tuple[list[str], str, str]] = [
    (["crude", "oil", "barrel", "wti", "petroleum", "brent"], "CL=F", "WTI Crude Oil (per barrel, USD)"),
    (["gold", "xau"], "GC=F", "Gold (per troy oz, USD)"),
    (["silver", "xag"], "SI=F", "Silver (per troy oz, USD)"),
    (["natural gas", "natgas"], "NG=F", "Natural Gas (per MMBtu, USD)"),
    (["corn"], "ZC=F", "Corn (per bushel, USc)"),
    (["wheat"], "ZW=F", "Wheat (per bushel, USc)"),
    (["bitcoin", "btc"], "BTC-USD", "Bitcoin (USD)"),
    (["ethereum", "eth"], "ETH-USD", "Ethereum (USD)"),
]

WEATHER_CODE_LABELS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Heavy rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Heavy thunderstorm with hail",
}

_WEATHER_KEYWORDS = {
    "weather",
    "temperature",
    "forecast",
    "humidity",
    "rain",
    "snow",
    "wind",
    "climate",
}


def is_weather_query(user_query: str) -> bool:
    """Return True when query appears to ask for weather conditions."""
    text = user_query.lower()
    return any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in _WEATHER_KEYWORDS)


_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_WEATHER_LOCATION_TIME_TAIL = re.compile(
    r"\s+\bfor\b\s+(?:the\s+)?(?:(?:coming|this|next)\s+)?"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|weekend|tomorrow)\b.*$",
    re.IGNORECASE,
)


def _normalize_weather_location_candidate(candidate: str) -> str:
    """Strip trailing time phrases accidentally captured as part of the place name."""
    normalized = candidate.strip(" .?,-")
    normalized = _WEATHER_LOCATION_TIME_TAIL.sub("", normalized).strip(" .?,-")
    normalized = re.sub(
        r"\s*\b(today|tonight|now|currently|right now|tomorrow|this (?:morning|afternoon|evening|week))\b\s*$",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip(" .?,-")
    return normalized


def extract_weather_location(user_query: str) -> str | None:
    """Extract location phrase from weather query, e.g. 'weather in Austin'."""
    if not is_weather_query(user_query):
        return None

    text = user_query.strip()

    # Prefer explicit "in <location>" or "for <location>" capture.
    for pattern in (
        r"\bin\s+([a-zA-Z][a-zA-Z\s,.-]{1,80})\??$",
        r"\bfor\s+([a-zA-Z][a-zA-Z\s,.-]{1,80})\??$",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = _normalize_weather_location_candidate(match.group(1))
            if candidate:
                return candidate

    # Fallback: remove common weather terms and use remaining words as place.
    cleaned = re.sub(
        r"\b(tell me|what is|what's|current|now|today|the|weather|temperature|forecast|humidity|rain|snow|wind|in|for)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:coming|this|next)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|weekend|tomorrow)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .?,-")
    if cleaned:
        return cleaned

    return None


def is_weather_forecast_query(user_query: str) -> bool:
    """True when the user asks for future weather, not conditions right now."""
    text = user_query.lower()
    if any(term in text for term in ("forecast", "tomorrow", "week", "weekly", "next", "coming")):
        return True
    if re.search(r"\bday\b", text):
        return True
    if re.search(
        r"\b(?:this|next|coming)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
    ):
        return True
    return False


def extract_forecast_days(user_query: str) -> int:
    """Extract forecast horizon from query, defaulting to 3 days."""
    text = user_query.lower()
    match = re.search(r"\b(\d{1,2})\s*[- ]?day\b", text)
    if match:
        try:
            return max(1, min(int(match.group(1)), 7))
        except ValueError:
            return 3
    if "weekly" in text or "week" in text:
        return 7
    if "tomorrow" in text:
        return 2

    weekday_match = re.search(
        r"\b(?:(next|coming|this)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
    )
    if weekday_match:
        modifier = weekday_match.group(1) or ""
        target = _WEEKDAY_INDEX[weekday_match.group(2)]
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).date()
        days_ahead = (target - today.weekday()) % 7
        if modifier == "next" and days_ahead == 0:
            days_ahead = 7
        return max(1, min(days_ahead + 1, 7))

    return 3


def is_news_query(user_query: str) -> bool:
    """Return True when query asks for latest/current news updates."""
    text = user_query.lower()
    news_terms = [
        "news",
        "headline",
        "headlines",
        "breaking",
        "latest updates",
        "latest on",
    ]
    return any(term in text for term in news_terms)


def extract_news_topic(user_query: str) -> str:
    """Extract topic phrase from news query; defaults to 'latest news'."""
    text = user_query.strip()

    on_match = re.search(r"\b(?:news|headlines|updates)\s+(?:about|on|for)\s+(.+)$", text, flags=re.IGNORECASE)
    if on_match:
        topic = on_match.group(1).strip(" .?,-")
        if topic:
            return topic

    about_match = re.search(r"\babout\s+(.+)$", text, flags=re.IGNORECASE)
    if about_match:
        topic = about_match.group(1).strip(" .?,-")
        if topic:
            return topic

    cleaned = re.sub(
        r"\b(tell me|what is|what's|latest|current|news|headlines|updates|breaking|on|about)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .?,-")
    return cleaned or "latest news"


def detect_commodity_query(user_query: str) -> tuple[str, str] | None:
    """Return (yahoo_ticker, label) if the query is about a tradable commodity/crypto."""
    text = user_query.lower()
    for keywords, ticker, label in _COMMODITY_MAP:
        if any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in keywords):
            return ticker, label
    return None


# ---------------------------------------------------------------------------
# Stock ticker helpers
# ---------------------------------------------------------------------------

# Words that look like tickers but are not
_NON_TICKER_WORDS = {
    "THE", "FOR", "AND", "NOT", "ARE", "YOU", "SHE", "HIM", "HER", "HIS",
    "USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD", "CHF", "CNY", "AED",
    "WTI", "XAU", "XAG",
    # Common English words that pattern-match as 1-5 char tickers
    "STOCK", "SHARE", "PRICE", "QUOTE", "WHAT", "GIVE", "SHOW", "TELL",
    "LIVE", "LAST", "OPEN", "REAL", "TIME", "DATA", "RATE", "NEWS",
    "GET", "CAN", "HAS", "ITS", "ALL", "ANY", "IS", "OF", "A", "AN", "IN",
    "ON", "AT", "TO", "DO", "IF", "OR", "AS", "BY", "UP", "SO", "NO", "GO",
    # Commodity/energy names
    "OIL", "GAS", "GOLD", "CORN", "COAL",
}

_STOCK_PATTERNS = [
    # "stock price of TDOC", "price of AAPL" — check before bare TICKER stock
    r"\b(?:stock|share|price|quote)\s+(?:of|for)\s+([A-Z]{1,5})\b",
    # "what is the stock price of TDOC"
    r"\bwhat\s+is\s+(?:the\s+)?(?:stock|share|price|quote)\s+(?:of|for)\s+([A-Z]{1,5})\b",
    # "what is TDOC stock", "what is MSFT price"
    r"\bwhat\s+is\s+(?:the\s+)?([A-Z]{1,5})\s+(?:stock|share|price|quote)\b",
    # "TDOC stock price", "AAPL stock", "TSLA shares"
    r"\b([A-Z]{1,5})\s+(?:stock|share|shares|price|quote)\b",
]


def detect_stock_query(user_query: str) -> str | None:
    """Extract a stock ticker from natural-language queries.

    Examples: 'TDOC stock price', 'what is AAPL stock', 'price of NVDA'.
    Returns uppercase ticker or None.
    """
    # Run patterns case-insensitively but capture original case
    for pat in _STOCK_PATTERNS:
        m = re.search(pat, user_query, re.IGNORECASE)
        if m:
            ticker = m.group(1).upper()
            if ticker not in _NON_TICKER_WORDS:
                return ticker
    return None


__all__ = [
    "WebSearchService",
    "should_use_web_search",
    "should_prioritize_fresh_web_data",
    "extract_currency_pair",
    "detect_commodity_query",
    "detect_stock_query",
    "is_weather_query",
    "is_weather_forecast_query",
    "extract_weather_location",
    "extract_forecast_days",
    "is_news_query",
    "extract_news_topic",
]
