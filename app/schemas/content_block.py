from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


ContentBlockType = Literal[
    "stock",
    "weather",
    "game_score",
    "crypto",
    "fx",
    "commodity",
    "flight",
    "transit",
    "traffic",
    "package",
    "air_quality",
    "service_status",
    "sun_times",
    "gas_price",
    "odds",
    "election",
    "news",
    "nearby_places",
    "text",
]


class ContentBlock(BaseModel):
    """Structured assistant content rendered as a purpose-built UI card."""

    type: ContentBlockType
    data: Dict[str, Any] = Field(default_factory=dict)
    subscription_key: Optional[str] = None


__all__ = ["ContentBlock", "ContentBlockType"]
