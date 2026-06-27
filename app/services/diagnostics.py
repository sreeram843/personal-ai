"""Environment diagnostics inspired by CLI /doctor checks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import text

from app.core.config import Settings
from app.services.health import check_ollama, check_qdrant, readiness_report
from app.services.mcp_store import McpServerStore
from app.services.skill_loader import SkillCatalog
from app.services.tool_registry import ToolRegistry


def _status(ok: bool, *, detail: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"status": "ok" if ok else "error"}
    if detail:
        payload["detail"] = detail
    return payload


async def check_postgres(settings: Settings, *, timeout: float = 5.0) -> Dict[str, Any]:
    del timeout  # sync SQLAlchemy session; kept for API consistency with other checks
    try:
        from app.db.session import get_session_factory

        db = get_session_factory()()
        try:
            db.execute(text("SELECT 1"))
            db.commit()
        finally:
            db.close()
        return _status(True)
    except Exception as exc:
        return _status(False, detail=str(exc))


async def check_redis(settings: Settings, *, timeout: float = 3.0) -> Dict[str, Any]:
    if not settings.redis_url:
        return {"status": "skipped", "detail": "REDIS_URL not configured"}
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=timeout)
        client.ping()
        return _status(True)
    except Exception as exc:
        return _status(False, detail=str(exc))


def _web_search_status(settings: Settings) -> Dict[str, Any]:
    providers: List[str] = []
    if settings.tavily_api_key:
        providers.append("tavily")
    if settings.perplexity_api_key:
        providers.append("perplexity")
    providers.append("duckduckgo")
    mode = settings.web_search_provider or "auto"
    return {
        "status": "ok" if providers else "warning",
        "provider_mode": mode,
        "available": providers,
        "tavily_configured": bool(settings.tavily_api_key),
        "perplexity_configured": bool(settings.perplexity_api_key),
    }


def _llm_status(settings: Settings) -> Dict[str, Any]:
    using_cloud = settings.llm_default_provider == "openai" and bool(settings.llm_openai_base_url)
    return {
        "status": "ok" if using_cloud or settings.ollama_base_url else "warning",
        "default_provider": settings.llm_default_provider,
        "default_model": settings.llm_default_model,
        "cloud_configured": using_cloud,
        "ollama_base_url": settings.ollama_base_url,
    }


async def build_doctor_report(
    *,
    settings: Settings,
    user_id: str,
    tool_registry: ToolRegistry,
    mcp_store: McpServerStore,
    skill_catalog: SkillCatalog,
) -> Dict[str, Any]:
    """Aggregate checks for the Agent settings diagnostics panel."""
    readiness = await readiness_report(settings=settings)
    postgres = await check_postgres(settings)
    redis = await check_redis(settings)

    mcp_servers = mcp_store.list_for_user(user_id) if settings.enable_runtime_mcp else []
    connected_mcp = sum(1 for item in mcp_servers if item.last_status == "connected")

    tools = tool_registry.list_tools_for_role("chat_agent")
    skills = skill_catalog.list_for_user(user_id)

    checks = {
        "readiness": readiness,
        "postgres": postgres,
        "redis": redis,
        "llm": _llm_status(settings),
        "web_search": _web_search_status(settings),
        "mcp": {
            "status": "ok" if not settings.enable_runtime_mcp or mcp_servers else "warning",
            "enabled": settings.enable_runtime_mcp,
            "servers": len(mcp_servers),
            "connected": connected_mcp,
        },
        "tools": {"status": "ok", "chat_agent_tools": len(tools)},
        "skills": {"status": "ok", "available": len(skills)},
    }

    critical = {"readiness", "postgres"}
    overall_ok = all(
        checks[name].get("status") in {"ok", "skipped", "warning"} or name not in critical
        for name in checks
    ) and readiness.get("status") in {"ready", "not_ready"}

    issues: List[str] = []
    if readiness.get("status") != "ready":
        issues.append("Core dependencies (Ollama/Qdrant) are not all reachable")
    if postgres.get("status") == "error":
        issues.append("PostgreSQL connection failed")
    if settings.enable_runtime_mcp and not mcp_servers:
        issues.append("Runtime MCP enabled but no servers configured")
    if not settings.tavily_api_key and not settings.perplexity_api_key:
        issues.append("No premium web search API key configured (DuckDuckGo fallback only)")

    return {
        "status": "healthy" if overall_ok and not issues else "degraded",
        "issues": issues,
        "features": {
            "fast_chat": settings.enable_fast_chat,
            "tool_agent": settings.enable_tool_agent,
            "runtime_mcp": settings.enable_runtime_mcp,
            "llm_history_compaction": settings.enable_llm_history_compaction,
            "user_memory": settings.enable_user_memory,
            "auth_disabled": settings.auth_disabled,
        },
        "checks": checks,
    }


__all__ = ["build_doctor_report"]
