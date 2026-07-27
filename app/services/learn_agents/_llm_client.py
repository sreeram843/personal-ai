"""Shared plain-chat helper for Agent Lab phases 3+.

Phase 1's minimal_agent.py is deliberately self-contained so the whole loop
fits on one screen. From Phase 3 onward there are several agents that all
need the same "send messages, get a message back" call against whichever
provider is configured — duplicating that boilerplate per file would just be
noise, so it lives here once.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import Settings


def endpoint_for(settings: Settings) -> tuple[str, Dict[str, str], Dict[str, Any], float]:
    """Return (url, headers, base_payload, timeout) for the configured LLM."""
    if settings.llm_default_provider == "openai" and settings.llm_openai_base_url:
        base = settings.llm_openai_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        headers = {"Content-Type": "application/json"}
        if settings.llm_openai_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_openai_api_key}"
        payload: Dict[str, Any] = {"model": settings.llm_default_model, "temperature": 0}
        return f"{base}/chat/completions", headers, payload, settings.llm_openai_timeout
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {"model": settings.ollama_chat_model, "stream": False}
    return url, {"Content-Type": "application/json"}, payload, 120.0


def extract_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the assistant message from OpenAI-style or Ollama responses."""
    if raw.get("choices"):
        return raw["choices"][0].get("message") or {}
    return raw.get("message") or {}


async def chat_completion(
    *,
    messages: List[Dict[str, Any]],
    settings: Settings,
    tools: Optional[List[Dict[str, Any]]] = None,
    stop: Optional[List[str]] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Call the configured LLM once. Returns (request_payload, raw_response)."""
    url, headers, base_payload, timeout = endpoint_for(settings)
    payload = {**base_payload, "messages": messages}
    if tools:
        payload["tools"] = tools
    if stop:
        payload["stop"] = stop
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return payload, response.json()


__all__ = ["endpoint_for", "extract_message", "chat_completion"]
