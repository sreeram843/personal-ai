"""Pluggable web search and scrape connectors (Tavily, Perplexity, Firecrawl)."""

from app.services.web_providers.router import scrape_url, web_search

__all__ = ["scrape_url", "web_search"]
