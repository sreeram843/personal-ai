"""Workflow run and checkpoint models for durable sessions."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Status of a workflow run."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    RESUMING = "resuming"
    CANCELLED = "cancelled"


class ErrorCategory(str, Enum):
    """Error classification for retry policies."""

    TRANSIENT = "transient"  # Retryable (network, timeout)
    PERMANENT = "permanent"  # Not retryable (invalid input)
    UNKNOWN = "unknown"


class WorkflowRunEventType(str, Enum):
    """Lifecycle event types for event-sourced run history."""

    RUN_CREATED = "run_created"
    STATUS_CHANGED = "status_changed"
    CHECKPOINT_ADDED = "checkpoint_added"
    CHECKPOINT_UPDATED = "checkpoint_updated"
    RUN_RETRIED = "run_retried"


class WorkflowRun(BaseModel):
    """A workflow execution run with full state."""

    run_id: str = Field(..., description="Unique run identifier")
    parent_run_id: Optional[str] = Field(None, description="Parent run if this is a retry/branch")
    mode: str = Field(..., description="Mode: 'chat', 'rag', or 'workflow'")
    conversation_id: Optional[str] = Field(None, description="Associated conversation ID")
    status: RunStatus = Field(default=RunStatus.PENDING, description="Current run status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start execution timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_category: Optional[ErrorCategory] = Field(None, description="Error classification for retry logic")
    error_fingerprint: Optional[str] = Field(None, description="Normalized error fingerprint for adaptive retries")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata/annotations")
    checkpoints: List["WorkflowCheckpoint"] = Field(default_factory=list, description="Step checkpoints")
    retry_count: int = Field(default=0, description="Number of retries performed")
    max_retries: int = Field(default=3, description="Max allowed retries")
    budget_limit_tokens: Optional[int] = Field(default=None, description="Optional per-run token budget")
    budget_used_tokens: int = Field(default=0, description="Approximate tokens used by the run")

    class Config:
        use_enum_values = False


class StepState(str, Enum):
    """State of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowCheckpoint(BaseModel):
    """Checkpoint of a workflow step for replay and resumption."""

    step_id: str = Field(..., description="Unique step identifier")
    run_id: str = Field(..., description="Associated run ID")
    agent: str = Field(..., description="Agent/role that executed this step")
    state: StepState = Field(default=StepState.PENDING, description="Step state")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution end time")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Step inputs for replay")
    outputs: Optional[str] = Field(None, description="Step output text")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_category: Optional[ErrorCategory] = Field(None, description="Error classification")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Step-specific metadata")
    depends_on: List[str] = Field(default_factory=list, description="IDs of dependency steps")
    retry_count: int = Field(default=0, description="Number of retries for this step")

    class Config:
        use_enum_values = False


class WorkflowRunEvent(BaseModel):
    """Append-only event record for workflow run state transitions."""

    event_id: str = Field(..., description="Unique event identifier")
    run_id: str = Field(..., description="Associated run ID")
    event_type: WorkflowRunEventType = Field(..., description="Type of lifecycle event")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")

    class Config:
        use_enum_values = False


class RetryPolicy(BaseModel):
    """Policy for retrying failed operations."""

    max_retries: int = Field(default=3, description="Maximum number of retries")
    initial_delay_seconds: float = Field(default=1.0, description="Initial retry delay")
    max_delay_seconds: float = Field(default=60.0, description="Max retry delay (with exponential backoff)")
    backoff_multiplier: float = Field(default=2.0, description="Exponential backoff multiplier")
    retryable_errors: List[ErrorCategory] = Field(
        default_factory=lambda: [ErrorCategory.TRANSIENT],
        description="Error categories that trigger retry",
    )

    def should_retry(self, error_category: ErrorCategory, retry_count: int) -> bool:
        """Check if an error should be retried."""
        return error_category in self.retryable_errors and retry_count < self.max_retries

    def get_retry_delay(self, retry_count: int) -> float:
        """Calculate delay for retry attempt (exponential backoff)."""
        delay = self.initial_delay_seconds * (self.backoff_multiplier ** retry_count)
        return min(delay, self.max_delay_seconds)


# Update forward refs for nested models
WorkflowRun.model_rebuild()
