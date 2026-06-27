"""Native tool-calling agent backed by ToolRegistry (no LangChain runtime)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.services.builtin_tools import CHAT_AGENT_ROLE
from app.services.llm_metrics import observe_llm_call
from app.services.tool_invocation import invoke_agent_tool, list_agent_tool_specs
from app.services.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 4


@dataclass
class ParsedToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMToolResponse:
    content: str = ""
    tool_calls: List[ParsedToolCall] = field(default_factory=list)


def _openai_compatible_base_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def build_openai_tool_definitions(registry: ToolRegistry, *, role: str) -> List[Dict[str, Any]]:
    """Convert registry tools to OpenAI/Ollama function-calling schema."""
    definitions: List[Dict[str, Any]] = []
    for tool_id, spec in list_agent_tool_specs(registry, role=role).items():
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": tool_id,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "User question or search terms (preferred).",
                            },
                            "user_query": {
                                "type": "string",
                                "description": "Alias for query.",
                            },
                        },
                        "additionalProperties": True,
                    },
                },
            }
        )
    return definitions


def _parse_tool_arguments(raw: Any) -> Dict[str, Any]:
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


def _parse_tool_calls(payload: Dict[str, Any]) -> LLMToolResponse:
    """Normalize OpenAI-compatible and Ollama chat responses."""
    message = payload.get("message") or {}
    if not message and payload.get("choices"):
        message = (payload["choices"][0].get("message") or {})

    content = str(message.get("content") or "").strip()
    tool_calls: List[ParsedToolCall] = []

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

    return LLMToolResponse(content=content, tool_calls=tool_calls)


def _build_messages(
    *,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    query: str,
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for item in chat_history:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        role = (item.get("role") or "user").lower()
        if role not in {"user", "assistant", "system"}:
            role = "user"
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": query})
    return messages


async def _chat_with_tools(
    *,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    settings: Settings,
) -> LLMToolResponse:
    if settings.llm_default_provider == "openai" and settings.llm_openai_base_url:
        url = f"{_openai_compatible_base_url(settings.llm_openai_base_url)}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if settings.llm_openai_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_openai_api_key}"
        payload = {
            "model": settings.llm_default_model,
            "messages": messages,
            "tools": tools,
            "temperature": 0,
        }
        timeout = settings.llm_openai_timeout
    else:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": settings.ollama_chat_model,
            "messages": messages,
            "tools": tools,
            "stream": False,
        }
        timeout = 120.0

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return _parse_tool_calls(response.json())


async def run_tool_agent(
    *,
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    tool_registry: ToolRegistry,
    settings: Settings,
    user_id: str | None = None,
) -> str:
    """Run a native tool-calling loop against ToolRegistry."""
    tools = build_openai_tool_definitions(tool_registry, role=CHAT_AGENT_ROLE)
    if not tools:
        raise RuntimeError("No tools registered for chat agent")

    specs = list_agent_tool_specs(tool_registry, role=CHAT_AGENT_ROLE)
    messages = _build_messages(system_prompt=system_prompt, chat_history=chat_history, query=query)
    extra_inputs = {"user_id": user_id} if user_id else None

    provider = settings.llm_default_provider
    model = settings.llm_default_model if provider == "openai" else settings.ollama_chat_model

    async with observe_llm_call(provider=provider, model=model):
        for _ in range(_MAX_ITERATIONS):
            llm_response = await _chat_with_tools(messages=messages, tools=tools, settings=settings)

            if not llm_response.tool_calls:
                if llm_response.content:
                    return llm_response.content
                return "ERROR 500: AGENT RETURNED NO OUTPUT"

            assistant_message: Dict[str, Any] = {
                "role": "assistant",
                "content": llm_response.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                    }
                    for call in llm_response.tool_calls
                ],
            }
            messages.append(assistant_message)

            for call in llm_response.tool_calls:
                spec = specs.get(call.name)
                if spec is None:
                    tool_output = f"ERROR: unknown tool '{call.name}'"
                else:
                    tool_output = await invoke_agent_tool(
                        tool_registry,
                        tool_id=call.name,
                        spec=spec,
                        role=CHAT_AGENT_ROLE,
                        arguments=call.arguments,
                        extra_inputs=extra_inputs,
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": tool_output,
                    }
                )

    logger.warning("Tool agent reached max iterations (%s)", _MAX_ITERATIONS)
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("content"):
            return str(message["content"])
    return "ERROR 500: AGENT RETURNED NO OUTPUT"


__all__ = [
    "build_openai_tool_definitions",
    "run_tool_agent",
]
