from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.chat import ChatMessage, ChatResponse


class DemoConfigResponse(BaseModel):
    enabled: bool
    max_questions: int
    intro: str
    full_app_url: Optional[str] = None
    suggested_prompts: List[str] = Field(default_factory=list)


class DemoChatRequest(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=128)
    message: str = Field(..., min_length=1, max_length=500)
    messages: List[ChatMessage] = Field(default_factory=list)


class DemoChatResponse(ChatResponse):
    questions_used: int
    questions_remaining: int
    limit_reached: bool
    full_app_url: Optional[str] = None
