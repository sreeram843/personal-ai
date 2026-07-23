from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx

from curai.config import LlmConfig


@dataclass
class ParsedToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LlmResponse:
    content: str = ""
    tool_calls: list[ParsedToolCall] = field(default_factory=list)


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"query": text}
        return parsed if isinstance(parsed, dict) else {"query": text}
    return {}


def _parse_response(payload: dict[str, Any]) -> LlmResponse:
    message = payload.get("message") or {}
    if not message and payload.get("choices"):
        message = (payload["choices"][0].get("message") or {})
    content = str(message.get("content") or "").strip()
    tool_calls: list[ParsedToolCall] = []
    for index, call in enumerate(message.get("tool_calls") or []):
        fn = call.get("function") or {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        tool_calls.append(
            ParsedToolCall(
                id=str(call.get("id") or f"call_{index}_{uuid4().hex[:8]}"),
                name=name,
                arguments=_parse_tool_arguments(fn.get("arguments")),
            )
        )
    return LlmResponse(content=content, tool_calls=tool_calls)


def _openai_base_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


class LlmClient:
    def __init__(self, config: LlmConfig) -> None:
        self._config = config

    async def chat_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LlmResponse:
        if self._config.provider == "openai":
            url = f"{_openai_base_url(self._config.base_url)}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self._config.api_key:
                headers["Authorization"] = f"Bearer {self._config.api_key}"
            payload = {
                "model": self._config.model,
                "messages": messages,
                "tools": tools,
                "temperature": 0,
            }
        else:
            url = f"{self._config.base_url.rstrip('/')}/api/chat"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self._config.model,
                "messages": messages,
                "tools": tools,
                "stream": False,
            }

        async with httpx.AsyncClient(timeout=self._config.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return _parse_response(response.json())
