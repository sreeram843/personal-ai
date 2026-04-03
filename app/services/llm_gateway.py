from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Sequence

import httpx

from app.services.ollama import OllamaClient


class LLMAdapter(Protocol):
    async def generate(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        model: str,
        options: Dict[str, Any],
    ) -> str:
        ...


class OllamaLLMAdapter:
    def __init__(self, client: OllamaClient) -> None:
        self._client = client

    async def generate(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        model: str,
        options: Dict[str, Any],
    ) -> str:
        response = await self._client.chat(messages, model=model, options=options, stream=False)
        content = str(response.get("message", {}).get("content") or "").strip()
        return content or "ERROR 500: AGENT RETURNED NO OUTPUT"


class OpenAICompatibleLLMAdapter:
    """Adapter for OpenAI-compatible chat completion endpoints.

    This supports hosted services that expose the `v1/chat/completions` contract.
    """

    def __init__(self, *, base_url: str, api_key: Optional[str], timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def generate(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        model: str,
        options: Dict[str, Any],
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "stream": False,
            **options,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenAI-compatible provider request failed: {exc}") from exc

        body = response.json()
        choices = body.get("choices") or []
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message") or {}
        content = str(message.get("content") or "").strip()
        return content or "ERROR 500: AGENT RETURNED NO OUTPUT"


@dataclass(frozen=True)
class StageModelConfig:
    provider: str
    model: str


@dataclass(frozen=True)
class WorkflowModelProfile:
    planner: StageModelConfig
    synthesizer: StageModelConfig
    reviewer: StageModelConfig
    writer: StageModelConfig


class LLMGateway:
    """Provider-dispatched text generation gateway.

    New providers can be added by registering another adapter under a provider key.
    """

    def __init__(self, adapters: Dict[str, LLMAdapter], default_provider: str = "ollama") -> None:
        self._adapters = adapters
        self._default_provider = default_provider

    async def generate(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        model: str,
        options: Dict[str, Any],
        provider: Optional[str] = None,
    ) -> str:
        selected_provider = provider or self._default_provider
        adapter = self._adapters.get(selected_provider)
        if adapter is None:
            raise RuntimeError(f"No LLM adapter registered for provider '{selected_provider}'")
        return await adapter.generate(messages=messages, model=model, options=options)


__all__ = [
    "LLMAdapter",
    "LLMGateway",
    "OllamaLLMAdapter",
    "OpenAICompatibleLLMAdapter",
    "StageModelConfig",
    "WorkflowModelProfile",
]
