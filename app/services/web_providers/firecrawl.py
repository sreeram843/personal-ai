from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"


async def firecrawl_scrape(
    *,
    url: str,
    api_key: str,
    timeout: float = 45.0,
    max_chars: int = 8000,
) -> str:
    target = (url or "").strip()
    if not target:
        return ""

    payload = {
        "url": target,
        "formats": ["markdown"],
        "onlyMainContent": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(FIRECRAWL_SCRAPE_URL, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
    except Exception as exc:
        logger.warning("Firecrawl scrape failed for %r: %s", target, exc)
        return ""

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return ""

    markdown = str(data.get("markdown") or "").strip()
    if not markdown:
        return ""
    if len(markdown) > max_chars:
        return markdown[:max_chars] + "\n…"
    return markdown


__all__ = ["firecrawl_scrape"]
