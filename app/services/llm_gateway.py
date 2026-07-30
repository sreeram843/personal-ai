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


# Sampling knobs some reasoning / Kimi models reject unless omitted or fixed at 1.
_SAMPLING_OPTION_KEYS = ("temperature", "top_p", "presence_penalty", "frequency_penalty")


def _model_locks_sampling_defaults(model: str) -> bool:
    """True when the vendor only allows default sampling (typically temperature=1 / omit)."""
    needle = (model or "").strip().lower()
    if not needle:
        return False
    # Kimi / Moonshot: "invalid temperature: only 1 is allowed for this model"
    if needle.startswith("kimi-") or needle.startswith("moonshot-"):
        return True
    # OpenAI reasoning family (o1/o3/o4) — custom temperature is unsupported.
    if needle.startswith(("o1", "o3", "o4")):
        return True
    # DeepSeek thinking / pro variants are happiest with defaults omitted.
    if needle in {"deepseek-v4-pro", "deepseek-reasoner"} or needle.endswith("-reasoner"):
        return True
    return False


def _apply_model_option_constraints(model: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Drop sampling params vendors reject when not at their fixed default."""
    if not _model_locks_sampling_defaults(model):
        return options
    constrained = dict(options)
    for key in _SAMPLING_OPTION_KEYS:
        constrained.pop(key, None)
    return constrained


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
        status = exc.response.status_code
        try:
            error_body = exc.response.json()
        except ValueError:
            error_body = exc.response.text
        if status == 429:
            return (
                f"OpenAI-compatible provider request failed (429): rate limit reached. "
                f"Wait a moment and try again, or switch to a higher-tier model/provider. Details: {error_body}"
            )
        return f"OpenAI-compatible provider request failed ({status}): {error_body}"
    if isinstance(exc, httpx.ReadTimeout):
        return (
            "OpenAI-compatible provider request timed out waiting for a response. "
            "Increase LLM_OPENAI_TIMEOUT for Chat, or LLM_ORCHESTRATED_TIMEOUT "
            "(e.g. 300–600) for Smart / workflow stages with slow models like Kimi or DeepSeek v4-pro."
        )
    return f"OpenAI-compatible provider request failed: {exc}"


def openai_compatible_chat_completions_url(base_url: str) -> str:
    """Build the chat-completions URL for an OpenAI-compatible provider root.

    Providers disagree on whether `/v1` is part of the base or the path:
    - Groq / DeepSeek / Fireworks: `{root}/v1/chat/completions`
    - Gemini OpenAI compat: `{.../v1beta/openai}/chat/completions`
    - OpenAI SDK style (`.../v1`): `{root}/chat/completions`
    - Perplexity Sonar: `{api.perplexity.ai}/chat/completions`
    """
    root = base_url.rstrip("/")
    lower = root.lower()
    if lower.endswith("/v1beta/openai") or "/v1beta/openai/" in lower:
        return f"{root}/chat/completions"
    if lower.endswith("/v1"):
        return f"{root}/chat/completions"
    if "api.perplexity.ai" in lower:
        return f"{root}/chat/completions"
    return f"{root}/v1/chat/completions"


# Provider-specific retired/renamed model ids.
_PROVIDER_MODEL_ALIASES: Dict[str, Dict[str, str]] = {
    "deepseek": {
        "deepseek-chat": "deepseek-v4-flash",
        "deepseek-reasoner": "deepseek-v4-pro",
        "deepseek-coder": "deepseek-v4-flash",
        # Common misconfig: Groq model ids pointed at DeepSeek.
        "llama-3.3-70b-versatile": "deepseek-v4-flash",
        "llama-3.1-8b-instant": "deepseek-v4-flash",
        "meta-llama/llama-4-scout-17b-16e-instruct": "deepseek-v4-flash",
    },
    # Groq: scout/qwen3-32b shut down 2026-07-17. Prefer current gpt-oss ids when
    # the project allowlist includes them; llama 3.1/3.3 shut down 2026-08-16.
    "groq": {
        "meta-llama/llama-4-scout-17b-16e-instruct": "openai/gpt-oss-20b",
        "llama-4-scout-17b-16e-instruct": "openai/gpt-oss-20b",
        "qwen/qwen3-32b": "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
        "llama-3.1-8b-instant": "openai/gpt-oss-20b",
        "gpt-oss-20b": "openai/gpt-oss-20b",
        "gpt-oss-120b": "openai/gpt-oss-120b",
    },
    # Cold-start env often labels the Groq endpoint as provider "openai".
    "openai": {
        "meta-llama/llama-4-scout-17b-16e-instruct": "openai/gpt-oss-20b",
        "llama-4-scout-17b-16e-instruct": "openai/gpt-oss-20b",
        "qwen/qwen3-32b": "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
        "llama-3.1-8b-instant": "openai/gpt-oss-20b",
        "gpt-oss-20b": "openai/gpt-oss-20b",
        "gpt-oss-120b": "openai/gpt-oss-120b",
    },
    # Moonshot/Kimi: kimi-k2.5 is unavailable to new accounts (sunset Aug 2026).
    "kimi": {
        "kimi-k2.5": "kimi-k2.6",
        "kimi-latest": "kimi-k3",
        "moonshot-v1-8k": "kimi-k2.6",
        "moonshot-v1-32k": "kimi-k2.6",
        "moonshot-v1-128k": "kimi-k2.6",
    },
    "moonshot": {
        "kimi-k2.5": "kimi-k2.6",
        "kimi-latest": "kimi-k3",
        "moonshot-v1-8k": "kimi-k2.6",
        "moonshot-v1-32k": "kimi-k2.6",
        "moonshot-v1-128k": "kimi-k2.6",
    },
}

# Remap by model id alone for Groq-only retired ids when the Admin provider
# label is ambiguous (e.g. cold-start provider named "openai" backed by Groq).
_GLOBAL_MODEL_ALIASES: Dict[str, str] = {
    "meta-llama/llama-4-scout-17b-16e-instruct": "openai/gpt-oss-20b",
    "llama-4-scout-17b-16e-instruct": "openai/gpt-oss-20b",
    "qwen/qwen3-32b": "openai/gpt-oss-20b",
    "kimi-k2.5": "kimi-k2.6",
    "kimi-latest": "kimi-k3",
}


def normalize_provider_model(provider: str, model: str) -> str:
    """Map deprecated provider model ids to current API names."""
    needle = (model or "").strip()
    if not needle:
        return model
    aliases = _PROVIDER_MODEL_ALIASES.get((provider or "").strip().lower())
    if aliases and needle in aliases:
        return aliases[needle]
    return _GLOBAL_MODEL_ALIASES.get(needle, model)


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
        # Cloudflare in front of some providers (notably Groq) returns 403/1010 for
        # httpx's default Python User-Agent. Use a plain client string instead.
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CurAI/1.0",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        request_timeout = self._timeout
        raw_timeout = options.get("timeout")
        if raw_timeout is not None:
            try:
                request_timeout = float(raw_timeout)
            except (TypeError, ValueError):
                request_timeout = self._timeout

        payload: Dict[str, Any] = {
            "model": model,
            "messages": _normalize_openai_messages(messages),
            "stream": False,
            **_apply_model_option_constraints(model, _coerce_openai_chat_options(options)),
        }

        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                response = await client.post(
                    openai_compatible_chat_completions_url(self._base_url),
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
        if adapter is None and selected_provider != self._default_provider:
            # Stage routing can briefly point at a provider before the gateway cache
            # rebuilds; fall back to the configured default so chat stays usable.
            adapter = self._adapters.get(self._default_provider)
            if adapter is not None:
                selected_provider = self._default_provider
        if adapter is None:
            available = ", ".join(sorted(self._adapters)) or "(none)"
            raise RuntimeError(
                f"No LLM adapter registered for provider '{provider or self._default_provider}'. "
                f"Available: {available}. Add/enable the provider in Admin and retry "
                "(or restart the app if routing was just changed)."
            )
        resolved_model = normalize_provider_model(selected_provider, model)
        async with observe_llm_call(provider=selected_provider, model=resolved_model):
            result = await adapter.generate(messages=messages, model=resolved_model, options=options)
        try:
            from app.services.usage_meter import record_llm_usage

            record_llm_usage(
                provider=selected_provider,
                model=resolved_model,
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
    "normalize_provider_model",
    "openai_compatible_chat_completions_url",
]
