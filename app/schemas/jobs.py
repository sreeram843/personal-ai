from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BackgroundJobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class BackgroundJobKind(str, Enum):
    INGEST = "ingest"
    WORKFLOW = "workflow"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BackgroundJob(BaseModel):
    job_id: str
    kind: BackgroundJobKind
    user_id: str
    status: BackgroundJobStatus = BackgroundJobStatus.QUEUED
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    run_id: Optional[str] = None


__all__ = ["BackgroundJob", "BackgroundJobKind", "BackgroundJobStatus"]
