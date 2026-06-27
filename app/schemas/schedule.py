from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ScheduleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    prompt: str = Field(..., min_length=1, max_length=4000)
    interval_minutes: int = Field(default=1440, ge=15, le=10080)


class ScheduledReportResponse(BaseModel):
    id: str
    title: str
    prompt: str
    interval_minutes: int
    enabled: bool
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_run_id: Optional[str] = None


class ScheduleListResponse(BaseModel):
    schedules: List[ScheduledReportResponse]


__all__ = [
    "ScheduleCreateRequest",
    "ScheduleListResponse",
    "ScheduledReportResponse",
]
