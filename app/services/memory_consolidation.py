"""
Memory consolidation and quality management service.

Handles memory tiering, consolidation, freshness decay, and retrieval ranking.
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional

from app.schemas.memory import MemoryConsolidationJob, MemoryEntry, MemoryQualityMetrics, MemoryTier


logger = logging.getLogger(__name__)


class MemoryConsolidationService:
    """Manages memory quality, consolidation, and tiering."""

    def __init__(self):
        """Initialize consolidation service."""
        self._entries: Dict[str, List[MemoryEntry]] = {}
        self._jobs: List[MemoryConsolidationJob] = []

    def add_entry(self, entry: MemoryEntry, conversation_id: str) -> None:
        """Add entry to memory store."""
        if conversation_id not in self._entries:
            self._entries[conversation_id] = []
        self._entries[conversation_id].append(entry)

    def retrieve_relevant(
        self,
        conversation_id: str,
        query: Optional[str] = None,
        tier: Optional[MemoryTier] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """
        Retrieve relevant memory entries with quality ranking.

        Scoring: 0.5 * recency_score + 0.3 * confidence + 0.2 * freshness
        """
        if conversation_id not in self._entries:
            return []

        entries = self._entries[conversation_id]

        # Filter by tier if specified
        if tier:
            entries = [e for e in entries if e.tier == tier]

        # Score and rank
        scored = []
        now = datetime.utcnow()
        for entry in entries:
            # Recency: entries accessed recently score higher
            age_hours = (now - entry.last_accessed).total_seconds() / 3600
            recency_score = max(0.0, 1.0 - (age_hours / 720))  # 30-day window

            # Final score
            score = 0.5 * recency_score + 0.3 * entry.confidence + 0.2 * entry.freshness

            scored.append((score, entry))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top entries
        return [e for _, e in scored[:limit]]

    def schedule_consolidation(self, conversation_id: str) -> MemoryConsolidationJob:
        """Schedule a consolidation job."""
        job = MemoryConsolidationJob(conversation_id=conversation_id, status="pending")
        self._jobs.append(job)
        return job

    def run_consolidation(self, job_id: str) -> bool:
        """
        Run consolidation job: merge, summarize, prune.

        Returns:
            True if successful, False otherwise
        """
        job = next((j for j in self._jobs if j.job_id == job_id), None)
        if not job:
            return False

        job.status = "running"

        try:
            entries = self._entries.get(job.conversation_id, [])

            # 1. Decay freshness
            for entry in entries:
                entry.update_freshness()

            # 2. Prune stale entries
            before_count = len(entries)
            entries = [e for e in entries if not e.is_stale()]
            job.entries_pruned = before_count - len(entries)

            # 3. Consolidate low-confidence entries
            low_conf = [e for e in entries if e.should_consolidate()]
            job.entries_merged = len(low_conf)

            # 4. Deduplicate similar entries (simple string matching)
            unique_entries = []
            seen_contents = set()
            for entry in entries:
                content_hash = hash(entry.content[:50])
                if content_hash not in seen_contents:
                    unique_entries.append(entry)
                    seen_contents.add(content_hash)
                else:
                    job.entries_merged += 1

            self._entries[job.conversation_id] = unique_entries
            job.entries_processed = len(unique_entries)
            job.status = "completed"
            job.summary = f"Processed {job.entries_processed}, merged {job.entries_merged}, pruned {job.entries_pruned}"

            return True
        except Exception as e:
            logger.error(f"Consolidation job {job_id} failed: {e}")
            job.status = "failed"
            job.summary = str(e)
            return False

    def get_metrics(self, conversation_id: str) -> MemoryQualityMetrics:
        """Get memory store health metrics."""
        entries = self._entries.get(conversation_id, [])

        by_tier = {}
        stale_count = 0
        low_conf_count = 0
        total_conf = 0.0

        for entry in entries:
            tier = entry.tier.value
            by_tier[tier] = by_tier.get(tier, 0) + 1

            if entry.is_stale():
                stale_count += 1
            if entry.confidence < 0.3:
                low_conf_count += 1

            total_conf += entry.confidence

        avg_conf = total_conf / len(entries) if entries else 0.5

        # Count pending jobs
        pending = sum(1 for j in self._jobs if j.conversation_id == conversation_id and j.status == "pending")

        # Find last consolidation
        last_consolidation = None
        for job in self._jobs:
            if job.conversation_id == conversation_id and job.status == "completed":
                if last_consolidation is None or job.created_at > last_consolidation:
                    last_consolidation = job.created_at

        return MemoryQualityMetrics(
            total_entries=len(entries),
            by_tier=by_tier,
            stale_entries=stale_count,
            low_confidence_entries=low_conf_count,
            avg_confidence=avg_conf,
            last_consolidation=last_consolidation,
            consolidation_jobs_pending=pending,
        )
