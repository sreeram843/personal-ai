from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    message: Optional[str] = Field(default=None, min_length=1)
    top_k: Optional[int] = Field(default=None, ge=1)
    score_threshold: Optional[float] = Field(default=None, ge=0.0)
    options: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def populate_messages(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        messages = values.get("messages")
        message = values.get("message")
        if (not messages or len(messages) == 0) and isinstance(message, str) and message.strip():
            values["messages"] = [{"role": "user", "content": message.strip()}]
        return values


class RetrievedChunk(BaseModel):
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]


class ChatResponse(BaseModel):
    message: str
    sources: List[RetrievedChunk]


__all__ = ["ChatMessage", "ChatRequest", "ChatResponse", "RetrievedChunk"]
