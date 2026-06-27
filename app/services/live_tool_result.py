from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.schemas.content_block import ContentBlock


@dataclass
class LiveToolResult:
    """Normalized output from a live-data tool — model text plus optional UI card."""

    summary: str
    block: Optional[ContentBlock] = None


__all__ = ["LiveToolResult"]
