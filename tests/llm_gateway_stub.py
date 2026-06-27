"""Shared helpers for LLM gateway test doubles."""

from __future__ import annotations

from app.services.llm_gateway import LLMGenerationResult


class LLMGatewayStubMixin:
    """Add ``generate_with_meta`` for stubs that only implement ``generate``."""

    async def generate_with_meta(self, *, messages, model: str, options, provider=None):
        result = await self.generate(messages=messages, model=model, options=options, provider=provider)
        if isinstance(result, LLMGenerationResult):
            return result
        return LLMGenerationResult(content=str(result))
