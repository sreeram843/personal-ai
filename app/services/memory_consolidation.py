"""
Memory consolidation and quality management service.

Handles memory tiering, consolidation, freshness decay, and retrieval ranking.
Entries are keyed by user_id and persisted as JSON (same pattern as UserMemoryStore).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.schemas.memory import MemoryConsolidationJob, MemoryEntry, MemoryQualityMetrics, MemoryTier


logger = logging.getLogger(__name__)


class MemoryConsolidationService:
    """Manages memory quality, consolidation, and tiering."""

    def __init__(self, file_path: Optional[str] = None):
        """Initialize consolidation service. Load persisted entries when file_path is set."""
        self._path = Path(file_path) if file_path else None
        self._jobs: List[MemoryConsolidationJob] = []
        self._entries: Dict[str, List[MemoryEntry]] = self._load()

    def add_entry(self, entry: MemoryEntry, conversation_id: str) -> None:
        """Add entry. Second argument is the store key (user_id)."""
        self.add_entry_for_user(entry, conversation_id)

    def add_entry_for_user(self, entry: MemoryEntry, user_id: str) -> None:
        """Add entry to the per-user memory store."""
        if not user_id:
            return
        if user_id not in self._entries:
            self._entries[user_id] = []
        self._entries[user_id].append(entry)
        self._persist()

    def record_turn(
        self,
        user_id: str,
        *,
        user_message: str,
        assistant_message: str = "",
    ) -> None:
        """Store a durable summary of a completed turn and run consolidation for that user."""
        if not user_id:
            return
        user_text = " ".join((user_message or "").split())[:200]
        if not user_text:
            return
        assistant_text = " ".join((assistant_message or "").split())[:160]
        content = f"User: {user_text}"
        if assistant_text:
            content = f"{content} Assistant: {assistant_text}"
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:16],
            tier=MemoryTier.DURABLE,
            content=content,
            confidence=0.8,
            freshness=1.0,
            access_count=2,
            category="conversation",
        )
        self.add_entry_for_user(entry, user_id)
        job = self.schedule_consolidation(user_id)
        self.run_consolidation(job.job_id)

    def retrieve_relevant(
        self,
        user_id: str,
        query: Optional[str] = None,
        tier: Optional[MemoryTier] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """
        Retrieve relevant memory entries with quality ranking.

        Scoring: 0.5 * recency_score + 0.3 * confidence + 0.2 * freshness
        """
        if user_id not in self._entries:
            return []

        entries = self._entries[user_id]

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

    def schedule_consolidation(self, user_id: str, conversation_id: str = "") -> MemoryConsolidationJob:
        """Schedule a consolidation job."""
        job = MemoryConsolidationJob(
            user_id=user_id,
            conversation_id=conversation_id,
            status="pending",
        )
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
        store_key = job.user_id or job.conversation_id

        try:
            entries = self._entries.get(store_key, [])

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

            self._entries[store_key] = unique_entries
            job.entries_processed = len(unique_entries)
            job.status = "completed"
            job.summary = f"Processed {job.entries_processed}, merged {job.entries_merged}, pruned {job.entries_pruned}"
            self._persist()

            return True
        except Exception as e:
            logger.error(f"Consolidation job {job_id} failed: {e}")
            job.status = "failed"
            job.summary = str(e)
            return False

    def get_metrics(self, user_id: str) -> MemoryQualityMetrics:
        """Get memory store health metrics."""
        entries = self._entries.get(user_id, [])

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

        def _job_user(job: MemoryConsolidationJob) -> str:
            return job.user_id or job.conversation_id

        # Count pending jobs
        pending = sum(1 for j in self._jobs if _job_user(j) == user_id and j.status == "pending")

        # Find last consolidation
        last_consolidation = None
        for job in self._jobs:
            if _job_user(job) == user_id and job.status == "completed":
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

    def _load(self) -> Dict[str, List[MemoryEntry]]:
        if not self._path or not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to read consolidation store at %s", self._path)
            return {}
        if not isinstance(raw, dict):
            return {}
        loaded: Dict[str, List[MemoryEntry]] = {}
        for user_id, bucket in raw.items():
            if isinstance(bucket, list):
                items = bucket
            elif isinstance(bucket, dict):
                items = bucket.get("entries") or []
            else:
                continue
            entries: List[MemoryEntry] = []
            for item in items:
                try:
                    entries.append(MemoryEntry.model_validate(item))
                except Exception:
                    continue
            loaded[str(user_id)] = entries
        return loaded

    def _persist(self) -> None:
        if not self._path:
            return
        data = {
            user_id: {"entries": [entry.model_dump(mode="json") for entry in entries]}
            for user_id, entries in self._entries.items()
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_memory_consolidation_service(*, file_path: str) -> MemoryConsolidationService:
    return MemoryConsolidationService(file_path=file_path)


__all__ = ["MemoryConsolidationService", "build_memory_consolidation_service"]
