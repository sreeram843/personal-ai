from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class WorkflowRequest(BaseModel):
    enabled: bool = True
    use_rag: bool = True
    include_trace: bool = True
    persist_memory: bool = True
    max_steps: int = Field(default=6, ge=2, le=12)
    reviewer_quorum: int = Field(default=2, ge=1, le=3)
    require_evidence_markers: bool = True
    trust_lanes_enabled: bool = True
    token_budget: Optional[int] = Field(default=None, ge=200)
    progressive_disclosure_level: Literal["compact", "full"] = "compact"


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    message: Optional[str] = Field(default=None, min_length=1)
    conversation_id: Optional[str] = Field(default=None, min_length=1)
    top_k: Optional[int] = Field(default=None, ge=1)
    score_threshold: Optional[float] = Field(default=None, ge=0.0)
    options: Dict[str, Any] = Field(default_factory=dict)
    workflow: Optional[WorkflowRequest] = None

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


class WorkflowStep(BaseModel):
    id: str
    agent: str
    title: str
    status: Literal["planned", "in_progress", "completed", "failed", "skipped"]
    summary: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)


class WorkflowTrace(BaseModel):
    mode: Literal["multi_agent"] = "multi_agent"
    status: Literal["completed", "failed", "partial"]
    run_id: Optional[str] = None
    steps: List[WorkflowStep] = Field(default_factory=list)


class ChatResponse(BaseModel):
    message: str
    sources: List[RetrievedChunk]
    workflow: Optional[WorkflowTrace] = None


__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "RetrievedChunk",
    "WorkflowRequest",
    "WorkflowStep",
    "WorkflowTrace",
]
