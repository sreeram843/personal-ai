from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence

import httpx

from app.services.llm_metrics import observe_llm_call
from app.services.ollama import OllamaClient

# OpenAI-compatible chat completion parameters (Groq, Together, etc.).
_OPENAI_CHAT_OPTION_KEYS = frozenset(
    {
        "temperature",
        "max_tokens",
        "max_completion_tokens",
        "top_p",
        "stop",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "response_format",
        "n",
        "logprobs",
        "top_logprobs",
        "user",
    }
)


@dataclass(frozen=True)
class LLMGenerationResult:
    content: str
    reasoning_content: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


class LLMAdapter(Protocol):
    async def generate(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        model: str,
        options: Dict[str, Any],
    ) -> LLMGenerationResult:
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
    ) -> LLMGenerationResult:
        response = await self._client.chat(messages, model=model, options=options, stream=False)
        content = str(response.get("message", {}).get("content") or "").strip()
        reasoning = str(response.get("message", {}).get("reasoning_content") or "").strip()
        text = content or "ERROR 500: AGENT RETURNED NO OUTPUT"
        prompt_tokens = response.get("prompt_eval_count")
        completion_tokens = response.get("eval_count")
        return LLMGenerationResult(
            content=text,
            reasoning_content=reasoning,
            prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
            completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
        )


def _coerce_openai_chat_options(options: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only parameters accepted by OpenAI-compatible chat completion APIs."""
    coerced: Dict[str, Any] = {}
    for key, value in options.items():
        if key not in _OPENAI_CHAT_OPTION_KEYS or value is None:
            continue
        coerced[key] = value
    return coerced


def _normalize_openai_messages(messages: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    """Merge consecutive system messages for stricter OpenAI-compatible providers."""
    normalized: List[Dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if normalized and role == "system" and normalized[-1]["role"] == "system":
            normalized[-1]["content"] = f"{normalized[-1]['content']}\n\n{content}"
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _format_openai_provider_error(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            error_body = exc.response.json()
        except ValueError:
            error_body = exc.response.text
        return f"OpenAI-compatible provider request failed ({exc.response.status_code}): {error_body}"
    return f"OpenAI-compatible provider request failed: {exc}"


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
    ) -> LLMGenerationResult:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": _normalize_openai_messages(messages),
            "stream": False,
            **_coerce_openai_chat_options(options),
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
            raise RuntimeError(_format_openai_provider_error(exc)) from exc

        body = response.json()
        choices = body.get("choices") or []
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message") or {}
        content = str(message.get("content") or "").strip()
        reasoning = str(message.get("reasoning_content") or "").strip()
        text = content or "ERROR 500: AGENT RETURNED NO OUTPUT"
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        return LLMGenerationResult(
            content=text,
            reasoning_content=reasoning,
            prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
            completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
        )


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
        result = await self.generate_with_meta(
            messages=messages,
            model=model,
            options=options,
            provider=provider,
        )
        return result.content

    async def generate_with_meta(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        model: str,
        options: Dict[str, Any],
        provider: Optional[str] = None,
    ) -> LLMGenerationResult:
        selected_provider = provider or self._default_provider
        adapter = self._adapters.get(selected_provider)
        if adapter is None:
            raise RuntimeError(f"No LLM adapter registered for provider '{selected_provider}'")
        async with observe_llm_call(provider=selected_provider, model=model):
            result = await adapter.generate(messages=messages, model=model, options=options)
        try:
            from app.services.usage_meter import record_llm_usage

            record_llm_usage(
                provider=selected_provider,
                model=model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
        except Exception:
            pass
        return result


__all__ = [
    "LLMAdapter",
    "LLMGateway",
    "LLMGenerationResult",
    "OllamaLLMAdapter",
    "OpenAICompatibleLLMAdapter",
    "StageModelConfig",
    "WorkflowModelProfile",
]
