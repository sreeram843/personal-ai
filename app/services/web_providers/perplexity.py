from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# Cheapest Perplexity tier: Search API ($0.005/request), not Pro Search ($0.008).
PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"


async def perplexity_search(
    *,
    query: str,
    api_key: str,
    max_results: int = 5,
    timeout: float = 20.0,
) -> List[Dict[str, Any]]:
    """Ranked web results via Perplexity Search API (structured snippets, no Sonar tokens)."""
    payload = {
        "query": query,
        "max_results": max(1, min(max_results, 20)),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(PERPLEXITY_SEARCH_URL, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
    except Exception as exc:
        logger.warning("Perplexity Search API failed for %r: %s", query, exc)
        return []

    results: List[Dict[str, Any]] = []
    for item in body.get("results") or []:
        if not isinstance(item, dict):
            continue
        href = str(item.get("url") or "").strip()
        title = str(item.get("title") or href or "Untitled").strip()
        snippet = str(item.get("snippet") or "").strip()
        if not href and not snippet:
            continue
        entry: Dict[str, Any] = {
            "title": title,
            "body": snippet,
            "href": href,
            "provider": "perplexity",
        }
        if item.get("date"):
            entry["date"] = item["date"]
        if item.get("last_updated"):
            entry["last_updated"] = item["last_updated"]
        results.append(entry)
    return results[:max_results]


__all__ = ["perplexity_search"]
