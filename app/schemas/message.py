"""
Agent communication schemas for typed inter-agent messaging.

Enables structured communication between agents with evidence tracking,
handoff summaries, and event streaming.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Types of inter-agent messages."""

    HANDOFF = "handoff"  # Agent handing off to another agent
    REQUEST = "request"  # Agent requesting action from another
    RESPONSE = "response"  # Agent responding to request
    EVENT = "event"  # System event (logging, state change)
    ERROR = "error"  # Error notification


class EvidenceType(str, Enum):
    """Types of evidence/artifacts."""

    CONTEXT = "context"  # Retrieved context, RAG results
    DRAFT = "draft"  # Draft text output
    REVIEW = "review"  # Review summary or feedback
    SEARCH_RESULT = "search_result"  # Web search results
    DECISION = "decision"  # Decision or judgment
    METRIC = "metric"  # Quality metric or score


class Evidence(BaseModel):
    """Immutable evidence object with unique ID."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Immutable evidence ID")
    type: EvidenceType = Field(..., description="Type of evidence")
    source_agent: str = Field(..., description="Agent that produced this evidence")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    content: str = Field(..., description="Evidence content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score (0-1)")

    class Config:
        frozen = True  # Make evidence immutable


class AgentMessage(BaseModel):
    """Inter-agent message with typed payload."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Message ID")
    type: MessageType = Field(..., description="Message type")
    from_agent: str = Field(..., description="Sending agent")
    to_agent: str = Field(..., description="Receiving agent")
    conversation_id: str = Field(..., description="Conversation this message belongs to")
    run_id: str = Field(..., description="Workflow run ID")
    step_id: Optional[str] = Field(default=None, description="Workflow step ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Message creation time")
    subject: str = Field(..., description="Message subject/title")
    body: str = Field(..., description="Message body/content")
    evidence: List[Evidence] = Field(default_factory=list, description="Supporting evidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    related_message_id: Optional[str] = Field(
        default=None, description="ID of related message (reply to, triggered by, etc.)"
    )


class HandoffSummary(BaseModel):
    """Summary of handoff between agents."""

    from_agent: str = Field(..., description="Agent handing off")
    to_agent: str = Field(..., description="Agent receiving handoff")
    step_id: str = Field(..., description="Step being handed off")
    summary: str = Field(..., description="What was accomplished and what's next")
    key_decisions: List[str] = Field(default_factory=list, description="Key decisions made")
    open_questions: List[str] = Field(default_factory=list, description="Unresolved questions")
    context_summary: str = Field(default="", description="Condensed context for next agent")
    evidence_count: int = Field(default=0, description="Number of evidence items passed")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Handoff confidence")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Handoff time")


class MessageEvent(BaseModel):
    """Event stream message for UI/monitoring."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Event ID")
    type: str = Field(..., description="Event type (message_received, handoff_complete, etc.)")
    run_id: str = Field(..., description="Workflow run ID")
    step_id: Optional[str] = Field(default=None, description="Step ID if applicable")
    agent: Optional[str] = Field(default=None, description="Agent involved")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    severity: str = Field(default="info", description="Severity: debug, info, warning, error")
