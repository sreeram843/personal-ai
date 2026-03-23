from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


AdapterStatus = Literal["ok", "partial", "error"]


class AdapterResult(BaseModel):
    """Normalized live-adapter response envelope."""

    domain: str
    status: AdapterStatus
    verified: bool = True
    source: str = ""
    provider_timestamp: Optional[str] = None
    fetched_at_utc: str
    ttl_seconds: int = 60
    data: Dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


__all__ = ["AdapterResult", "AdapterStatus"]
