from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

LiveDomain = Literal[
    "fx",
    "commodity",
    "stock",
    "weather_current",
    "weather_forecast",
    "news",
    "game_score",
    "generic_fresh",
]


class LiveIntent(BaseModel):
    """Structured live-data intent with extracted slots."""

    domain: LiveDomain
    slots: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class LiveDataProvenance(BaseModel):
    """Machine-readable provenance for verified live adapter responses."""

    domain: str
    source: str
    fetched_at_utc: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verified: bool = True
    provider_timestamp: Optional[str] = None


__all__ = ["LiveDomain", "LiveIntent", "LiveDataProvenance"]
