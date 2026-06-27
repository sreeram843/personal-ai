from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


async def tavily_search(
    *,
    query: str,
    api_key: str,
    max_results: int = 5,
    timeout: float = 15.0,
) -> List[Dict[str, Any]]:
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "search_depth": "basic",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            body = response.json()
    except Exception as exc:
        logger.warning("Tavily search failed for %r: %s", query, exc)
        return []

    results: List[Dict[str, Any]] = []
    for item in body.get("results") or []:
        if not isinstance(item, dict):
            continue
        href = str(item.get("url") or "").strip()
        title = str(item.get("title") or href or "Untitled").strip()
        content = str(item.get("content") or "").strip()
        if not href and not content:
            continue
        results.append(
            {
                "title": title,
                "body": content,
                "href": href,
                "score": item.get("score"),
                "provider": "tavily",
            }
        )
    return results


__all__ = ["tavily_search"]
