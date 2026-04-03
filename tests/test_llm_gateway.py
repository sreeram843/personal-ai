from __future__ import annotations

import asyncio

import httpx

from app.services.llm_gateway import LLMGateway, OpenAICompatibleLLMAdapter


class _RecordingAdapter:
    def __init__(self, label: str) -> None:
        self.label = label
        self.calls = 0

    async def generate(self, *, messages, model: str, options):
        self.calls += 1
        return f"{self.label}:{model}"


def test_llm_gateway_dispatches_selected_provider() -> None:
    ollama = _RecordingAdapter("ollama")
    openai = _RecordingAdapter("openai")
    gateway = LLMGateway(adapters={"ollama": ollama, "openai": openai}, default_provider="ollama")

    output = asyncio.run(
        gateway.generate(
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
            options={},
            provider="openai",
        )
    )

    assert output == "openai:test-model"
    assert ollama.calls == 0
    assert openai.calls == 1


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

    assert output == "Adapter output"
