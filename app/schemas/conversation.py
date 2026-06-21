from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    mode: Optional[str] = Field(default="smart", max_length=32)


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    pinned: Optional[bool] = None


class ConversationSummary(BaseModel):
    id: str
    title: Optional[str] = None
    mode: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    pinned: bool = False
    pinned_at: Optional[datetime] = None


class StoredMessageResponse(BaseModel):
    id: str
    role: Literal["system", "user", "assistant"]
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationListResponse(BaseModel):
    conversations: List[ConversationSummary]


class ConversationMessagesResponse(BaseModel):
    conversation_id: str
    messages: List[StoredMessageResponse]


__all__ = [
    "ConversationListResponse",
    "ConversationMessagesResponse",
    "ConversationSummary",
    "CreateConversationRequest",
    "StoredMessageResponse",
    "UpdateConversationRequest",
]
