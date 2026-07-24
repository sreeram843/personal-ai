from __future__ import annotations

import asyncio

import httpx

from app.services.llm_gateway import (
    LLMGateway,
    LLMGenerationResult,
    OpenAICompatibleLLMAdapter,
    _coerce_openai_chat_options,
    _format_openai_provider_error,
    _normalize_openai_messages,
    normalize_provider_model,
    openai_compatible_chat_completions_url,
)


def test_openai_compatible_chat_completions_url_variants() -> None:
    assert (
        openai_compatible_chat_completions_url("https://api.groq.com/openai")
        == "https://api.groq.com/openai/v1/chat/completions"
    )
    assert (
        openai_compatible_chat_completions_url("https://api.deepseek.com")
        == "https://api.deepseek.com/v1/chat/completions"
    )
    assert (
        openai_compatible_chat_completions_url("https://api.openai.com/v1")
        == "https://api.openai.com/v1/chat/completions"
    )
    assert (
        openai_compatible_chat_completions_url("https://api.perplexity.ai")
        == "https://api.perplexity.ai/chat/completions"
    )
    assert (
        openai_compatible_chat_completions_url(
            "https://generativelanguage.googleapis.com/v1beta/openai"
        )
        == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )


class _RecordingAdapter:
    def __init__(self, label: str) -> None:
        self.label = label
        self.calls = 0

    async def generate(self, *, messages, model: str, options):
        self.calls += 1
        return LLMGenerationResult(content=f"{self.label}:{model}")


def test_format_openai_provider_error_read_timeout_message() -> None:
    message = _format_openai_provider_error(httpx.ReadTimeout("timed out"))
    assert "timed out" in message.lower()
    assert "LLM_OPENAI_TIMEOUT" in message


def test_normalize_provider_model_deepseek_aliases() -> None:
    assert normalize_provider_model("deepseek", "deepseek-chat") == "deepseek-v4-flash"
    assert normalize_provider_model("deepseek", "deepseek-reasoner") == "deepseek-v4-pro"
    assert normalize_provider_model("deepseek", "deepseek-v4-flash") == "deepseek-v4-flash"
    assert normalize_provider_model("groq", "deepseek-chat") == "deepseek-chat"


def test_normalize_provider_model_retired_groq_aliases() -> None:
    scout = "meta-llama/llama-4-scout-17b-16e-instruct"
    assert normalize_provider_model("groq", scout) == "llama-3.1-8b-instant"
    # Provider may be labeled openai while still using Groq model ids.
    assert normalize_provider_model("openai", scout) == "llama-3.1-8b-instant"
    assert normalize_provider_model("groq", "qwen/qwen3-32b") == "llama-3.3-70b-versatile"
    assert normalize_provider_model("groq", "openai/gpt-oss-20b") == "llama-3.1-8b-instant"
    assert normalize_provider_model("deepseek", "llama-3.3-70b-versatile") == "deepseek-v4-flash"


def test_llm_gateway_falls_back_to_default_provider() -> None:
    default = _RecordingAdapter("groq")
    gateway = LLMGateway(adapters={"groq": default}, default_provider="groq")

    output = asyncio.run(
        gateway.generate(
            messages=[{"role": "user", "content": "hi"}],
            model="deepseek-chat",
            options={},
            provider="deepseek",
        )
    )

    assert output == "groq:deepseek-chat"
    assert default.calls == 1


def test_llm_gateway_rewrites_deepseek_model_ids() -> None:
    deepseek = _RecordingAdapter("deepseek")
    gateway = LLMGateway(adapters={"deepseek": deepseek}, default_provider="deepseek")

    output = asyncio.run(
        gateway.generate(
            messages=[{"role": "user", "content": "hi"}],
            model="deepseek-chat",
            options={},
            provider="deepseek",
        )
    )

    assert output == "deepseek:deepseek-v4-flash"
    assert deepseek.calls == 1


def test_openai_compatible_adapter_parses_chat_completion() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = request.read().decode("utf-8")
        assert "model" in payload
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-local",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Adapter output"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            },
        )

    transport = httpx.MockTransport(_handler)

    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    original_client = httpx.AsyncClient
    httpx.AsyncClient = _MockAsyncClient
    try:
        adapter = OpenAICompatibleLLMAdapter(base_url="http://localhost:1234", api_key=None, timeout=10.0)
        output = asyncio.run(
            adapter.generate(
                messages=[{"role": "user", "content": "hello"}],
                model="local-model",
                options={},
            )
        )
    finally:
        httpx.AsyncClient = original_client

    assert output.content == "Adapter output"
    assert output.prompt_tokens == 12
    assert output.completion_tokens == 4


def test_openai_compatible_adapter_strips_workflow_options() -> None:
    import json

    captured_payload: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            },
        )

    transport = httpx.MockTransport(_handler)

    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    original_client = httpx.AsyncClient
    httpx.AsyncClient = _MockAsyncClient
    try:
        adapter = OpenAICompatibleLLMAdapter(base_url="http://localhost:1234", api_key=None, timeout=10.0)
        asyncio.run(
            adapter.generate(
                messages=[
                    {"role": "system", "content": "base"},
                    {"role": "system", "content": "extra"},
                    {"role": "user", "content": "hello"},
                ],
                model="local-model",
                options={
                    "temperature": 0.2,
                    "reviewer_quorum": 2,
                    "require_evidence_markers": True,
                    "trust_lanes_enabled": True,
                    "progressive_disclosure_level": "compact",
                    "token_budget": None,
                },
            )
        )
    finally:
        httpx.AsyncClient = original_client

    assert captured_payload["temperature"] == 0.2
    assert "reviewer_quorum" not in captured_payload
    assert "trust_lanes_enabled" not in captured_payload
    assert captured_payload["messages"] == [
        {"role": "system", "content": "base\n\nextra"},
        {"role": "user", "content": "hello"},
    ]


def test_coerce_openai_chat_options_ignores_unknown_keys() -> None:
    assert _coerce_openai_chat_options(
        {
            "temperature": 0.1,
            "max_tokens": 256,
            "reviewer_quorum": 2,
            "token_budget": None,
        }
    ) == {"temperature": 0.1, "max_tokens": 256}


def test_normalize_openai_messages_merges_system_prompts() -> None:
    assert _normalize_openai_messages(
        [
            {"role": "system", "content": "one"},
            {"role": "system", "content": "two"},
            {"role": "user", "content": "question"},
        ]
    ) == [
        {"role": "system", "content": "one\n\ntwo"},
        {"role": "user", "content": "question"},
    ]
