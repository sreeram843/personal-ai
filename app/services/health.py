from __future__ import annotations

from typing import Any, Dict

import httpx

from app.core.config import Settings


async def check_ollama(settings: Settings, *, timeout: float = 5.0) -> Dict[str, Any]:
    """Return Ollama reachability status."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            response = await http.get(url)
            response.raise_for_status()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def check_qdrant(settings: Settings, *, timeout: float = 5.0) -> Dict[str, Any]:
    """Return Qdrant reachability status."""
    base = settings.qdrant_url.rstrip("/")
    url = f"{base}/collections"
    headers: Dict[str, str] = {}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            response = await http.get(url, headers=headers or None)
            response.raise_for_status()
        return {"status": "ok", "collection": settings.qdrant_collection}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def readiness_report(
    *,
    settings: Settings,
) -> Dict[str, Any]:
    """Aggregate dependency checks for GET /ready."""
    ollama_status = await check_ollama(settings)
    qdrant_status = await check_qdrant(settings)
    checks = {
        "ollama": ollama_status,
        "qdrant": qdrant_status,
    }
    ready = all(item.get("status") == "ok" for item in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "app": settings.app_name,
        "checks": checks,
    }
