from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.services.web_providers.firecrawl import firecrawl_scrape
from app.services.web_providers.perplexity import perplexity_search
from app.services.web_providers.tavily import tavily_search

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

SearchResult = Dict[str, Any]


def resolve_search_provider(settings: "Settings") -> str:
    configured = (settings.web_search_provider or "auto").strip().lower()
    if configured not in {"auto", "tavily", "perplexity", "duckduckgo"}:
        return "auto"
    if configured != "auto":
        return configured
    if settings.tavily_api_key:
        return "tavily"
    if settings.perplexity_api_key:
        return "perplexity"
    return "duckduckgo"


async def web_search(
    *,
    query: str,
    settings: "Settings",
    max_results: int = 5,
    timeout: float = 15.0,
    fallback: Optional[List[SearchResult]] = None,
) -> List[SearchResult]:
    """Search via configured provider with Tavily → Perplexity fallback chain."""
    provider = resolve_search_provider(settings)
    if provider == "duckduckgo":
        return fallback or []

    if provider in {"auto", "tavily"} and settings.tavily_api_key:
        results = await tavily_search(
            query=query,
            api_key=settings.tavily_api_key,
            max_results=max_results,
            timeout=timeout,
        )
        if results:
            return results

    if provider in {"auto", "perplexity", "tavily"} and settings.perplexity_api_key:
        results = await perplexity_search(
            query=query,
            api_key=settings.perplexity_api_key,
            max_results=max_results,
            timeout=max(timeout, 20.0),
        )
        if results:
            return results

    return fallback or []


async def scrape_url(
    *,
    url: str,
    settings: "Settings",
    timeout: float = 45.0,
    max_chars: int = 8000,
) -> str:
    if settings.firecrawl_api_key:
        markdown = await firecrawl_scrape(
            url=url,
            api_key=settings.firecrawl_api_key,
            timeout=timeout,
            max_chars=max_chars,
        )
        if markdown:
            return markdown
    return ""


__all__ = ["resolve_search_provider", "scrape_url", "web_search"]
