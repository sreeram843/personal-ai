from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestDocument(BaseModel):
    id: Optional[str] = None
    text: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: List[IngestDocument]


class IngestResponse(BaseModel):
    count: int


__all__ = ["IngestDocument", "IngestRequest", "IngestResponse"]
