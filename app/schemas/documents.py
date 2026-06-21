from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.jobs import BackgroundJobStatus


class IngestDocument(BaseModel):
    id: Optional[str] = None
    text: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: List[IngestDocument]


class IngestResponse(BaseModel):
    count: Optional[int] = None
    job_id: Optional[str] = None
    status: Optional[BackgroundJobStatus] = None


__all__ = ["IngestDocument", "IngestRequest", "IngestResponse"]
