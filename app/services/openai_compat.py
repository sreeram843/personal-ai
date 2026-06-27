"""OpenAI-compatible chat API adapter."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from app.core.config import Settings
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse

StrategyOverride = Literal["fast", "tools", "orchestrated"]


def list_openai_models(settings: Settings) -> dict[str, Any]:
    models = [
        {
            "id": "curai-default",
            "object": "model",
            "created": 0,
            "owned_by": settings.app_name,
        },
        {
            "id": "curai-tools",
            "object": "model",
            "created": 0,
            "owned_by": settings.app_name,
        },
        {
            "id": "curai-fast",
            "object": "model",
            "created": 0,
            "owned_by": settings.app_name,
        },
    ]
    return {"object": "list", "data": models}


def strategy_override_for_model(model: str) -> Optional[StrategyOverride]:
    normalized = (model or "").strip().lower()
    if normalized in {"curai-tools", "curai-tool-agent"}:
        return "tools"
    if normalized in {"curai-fast", "curai-fast-chat"}:
        return "fast"
    if normalized in {"curai-default", "curai", "gpt-4", "gpt-4o", "gpt-3.5-turbo"}:
        return None
    return None


def chat_request_from_openai(body: dict[str, Any]) -> ChatRequest:
    raw_messages = body.get("messages") or []
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError("messages must be a non-empty array")

    messages: List[ChatMessage] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").lower()
        if role not in {"system", "user", "assistant"}:
            role = "user"
        content = item.get("content")
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text") or ""))
            content = "\n".join(part for part in text_parts if part)
        text = str(content or "").strip()
        if not text:
            continue
        messages.append(ChatMessage(role=role, content=text))

    if not messages:
        raise ValueError("messages must include at least one non-empty entry")

    options: Dict[str, Any] = {}
    model = str(body.get("model") or "curai-default")
    override = strategy_override_for_model(model)
    if override:
        options["force_strategy"] = override

    user_data = body.get("user")
    if user_data is not None:
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        if isinstance(metadata, dict) and metadata.get("assistant_id"):
            options["assistant_id"] = metadata["assistant_id"]
        if body.get("assistant_id"):
            options["assistant_id"] = body["assistant_id"]

    conversation_id = None
    metadata = body.get("metadata")
    if isinstance(metadata, dict):
        conversation_id = metadata.get("conversation_id")
        if metadata.get("assistant_id"):
            options["assistant_id"] = metadata["assistant_id"]

    return ChatRequest(
        messages=messages,
        conversation_id=str(conversation_id).strip() if conversation_id else None,
        options=options,
    )


def openai_completion_from_response(*, response: ChatResponse, model: str) -> dict[str, Any]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.message},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": response.prompt_tokens or 0,
            "completion_tokens": response.completion_tokens or 0,
            "total_tokens": (response.prompt_tokens or 0) + (response.completion_tokens or 0),
        },
    }


async def stream_openai_chunks_from_sse(
    *,
    sse_events: AsyncIterator[str],
    model: str,
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    async for event in sse_events:
        if not event.startswith("data: "):
            continue
        body = event[6:].strip()
        if not body:
            continue
        payload = json.loads(body)
        event_type = payload.get("type")
        if event_type == "status":
            continue
        if event_type == "block":
            continue
        if event_type == "final":
            response = ChatResponse.model_validate(payload.get("response") or {})
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": response.message}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return
        if event_type == "error":
            raise RuntimeError(str(payload.get("message") or "stream failed"))


__all__ = [
    "chat_request_from_openai",
    "list_openai_models",
    "openai_completion_from_response",
    "stream_openai_chunks_from_sse",
    "strategy_override_for_model",
]
