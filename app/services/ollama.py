from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx


class OllamaClient:
    """Lightweight async client for interacting with a local Ollama server."""

    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embed_model: str,
        *,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embed_model = embed_model
        self._timeout = timeout

    async def chat(
        self,
        messages: Sequence[Dict[str, str]],
        *,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Send a chat completion request and return the JSON response."""

        payload: Dict[str, Any] = {
            "model": self._chat_model,
            "messages": list(messages),
            "stream": stream,
        }
        if options:
            payload["options"] = options

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    async def embed(self, inputs: Iterable[str]) -> List[List[float]]:
        """Generate embeddings for one or more input strings."""

        items = list(inputs)
        if not items:
            return []

        payload = {"model": self._embed_model, "input": items}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/embed", json=payload)
            response.raise_for_status()
            data = response.json()

        if "embeddings" in data:
            return data["embeddings"]
        if "embedding" in data:
            # Ollama returns a singular "embedding" field for one-off requests.
            return [data["embedding"]]
        raise RuntimeError("Unexpected response format from Ollama embed endpoint")


__all__ = ["OllamaClient"]
