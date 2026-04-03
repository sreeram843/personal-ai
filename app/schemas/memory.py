"""
Memory quality and consolidation system.

Implements memory tiering, background consolidation, freshness tracking,
and intelligent retrieval ranking.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryTier(str, Enum):
    """Memory tiering levels."""

    EPHEMERAL = "ephemeral"  # Session-only, fast decay
    CONVERSATION = "conversation"  # Current conversation scope
    DURABLE = "durable"  # User-level, persistent


class MemoryEntry(BaseModel):
    """Memory entry with quality metadata."""

    id: str = Field(..., description="Unique entry ID")
    tier: MemoryTier = Field(..., description="Memory tier")
    content: str = Field(..., description="Memory content")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = Field(default=0, description="How many times accessed")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score")
    freshness: float = Field(default=1.0, ge=0.0, le=1.0, description="Freshness score (0=stale, 1=fresh)")
    category: str = Field(default="general", description="Memory category")
    related_entries: List[str] = Field(default_factory=list, description="Related entry IDs")
    ttl_hours: Optional[int] = Field(default=None, description="Time-to-live in hours")
    embedding_vector: Optional[List[float]] = Field(default=None, description="Embedding for similarity search")

    def is_stale(self) -> bool:
        """Check if entry is stale based on TTL and age."""
        if self.ttl_hours:
            age = datetime.utcnow() - self.created_at
            return age > timedelta(hours=self.ttl_hours)
        return self.freshness < 0.2

    def should_consolidate(self) -> bool:
        """Check if entry should be consolidated (merged/summarized)."""
        return self.confidence < 0.3 or self.access_count < 2

    def update_freshness(self) -> None:
        """Decay freshness over time."""
        age_hours = (datetime.utcnow() - self.created_at).total_seconds() / 3600
        # Exponential decay: freshness = e^(-age/halflife)
        halflife_hours = 168  # 1 week
        import math
        self.freshness = max(0.0, math.exp(-age_hours / halflife_hours))


class MemoryConsolidationJob(BaseModel):
    """Background consolidation job configuration."""

    job_id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex[:16])
    conversation_id: str = Field(...)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending")  # pending, running, completed, failed
    entries_processed: int = Field(default=0)
    entries_merged: int = Field(default=0)
    entries_pruned: int = Field(default=0)
    summary: str = Field(default="")


class MemoryQualityMetrics(BaseModel):
    """Metrics for memory store health."""

    total_entries: int
    by_tier: Dict[str, int]
    stale_entries: int
    low_confidence_entries: int
    avg_confidence: float
    last_consolidation: Optional[datetime]
    consolidation_jobs_pending: int
