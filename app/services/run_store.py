"""Run store for persisting workflow runs and checkpoints."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from app.schemas.run import (
    ErrorCategory,
    RetryPolicy,
    RunStatus,
    WorkflowCheckpoint,
    WorkflowRun,
    WorkflowRunEvent,
    WorkflowRunEventType,
)

logger = logging.getLogger(__name__)


class RunStore:
    """Stores and retrieves workflow runs with checkpoints."""

    def __init__(self, storage_path: str = "memory/runs") -> None:
        """Initialize run store.

        Args:
            storage_path: Directory path for persisting runs
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, WorkflowRun] = {}
        self._event_cache: Dict[str, List[WorkflowRunEvent]] = {}
        self._retry_policy = RetryPolicy()

    def create_run(self, mode: str, conversation_id: Optional[str] = None, run_id: str = None) -> WorkflowRun:
        """Create a new workflow run.

        Args:
            mode: Workflow mode ('chat', 'rag', 'workflow')
            conversation_id: Optional associated conversation
            run_id: Optional custom run ID (auto-generated if not provided)

        Returns:
            Created WorkflowRun
        """
        if run_id is None:
            run_id = f"run_{datetime.utcnow().timestamp()}"

        run = WorkflowRun(run_id=run_id, mode=mode, conversation_id=conversation_id)
        self._cache[run_id] = run
        self._persist_run(run)
        self._append_event(
            run_id,
            WorkflowRunEventType.RUN_CREATED,
            {
                "mode": mode,
                "conversation_id": conversation_id,
                "status": run.status.value,
            },
        )
        logger.info(f"Created run {run_id}")
        return run

    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Get run by ID."""
        if run_id in self._cache:
            return self._cache[run_id]

        # Try loading from storage
        run = self._load_run(run_id)
        if run:
            self._cache[run_id] = run
        return run

    def update_run_status(self, run_id: str, status: RunStatus, error: Optional[str] = None) -> Optional[WorkflowRun]:
        """Update run status."""
        run = self.get_run(run_id)
        if not run:
            return None

        run.status = status
        if status == RunStatus.IN_PROGRESS and run.started_at is None:
            run.started_at = datetime.utcnow()
        elif status == RunStatus.COMPLETED:
            run.completed_at = datetime.utcnow()
        elif status == RunStatus.FAILED:
            run.error = error
            run.error_fingerprint = self._compute_error_fingerprint(error)
            run.error_category = self._classify_error_category(error)
            run.completed_at = datetime.utcnow()

        self._persist_run(run)
        self._append_event(
            run_id,
            WorkflowRunEventType.STATUS_CHANGED,
            {
                "status": status.value,
                "error": error,
                "error_category": run.error_category.value if run.error_category else None,
                "error_fingerprint": run.error_fingerprint,
            },
        )
        return run

    def add_checkpoint(self, run_id: str, checkpoint: WorkflowCheckpoint) -> Optional[WorkflowRun]:
        """Add step checkpoint to run."""
        run = self.get_run(run_id)
        if not run:
            return None

        run.checkpoints.append(checkpoint)
        self._persist_run(run)
        self._append_event(
            run_id,
            WorkflowRunEventType.CHECKPOINT_ADDED,
            {
                "step_id": checkpoint.step_id,
                "agent": checkpoint.agent,
                "state": checkpoint.state.value,
                "depends_on": checkpoint.depends_on,
            },
        )
        logger.debug(f"Added checkpoint {checkpoint.step_id} to run {run_id}")
        return run

    def update_checkpoint(self, run_id: str, step_id: str, state: str, output: Optional[str] = None, error: Optional[str] = None) -> Optional[WorkflowCheckpoint]:
        """Update checkpoint state and result."""
        run = self.get_run(run_id)
        if not run:
            return None

        checkpoint = next((c for c in run.checkpoints if c.step_id == step_id), None)
        if not checkpoint:
            return None

        checkpoint.state = state
        if output:
            checkpoint.outputs = output
            checkpoint.completed_at = datetime.utcnow()
        if error:
            checkpoint.error = error

        self._persist_run(run)
        self._append_event(
            run_id,
            WorkflowRunEventType.CHECKPOINT_UPDATED,
            {
                "step_id": checkpoint.step_id,
                "state": checkpoint.state.value,
                "error": checkpoint.error,
            },
        )
        return checkpoint

    def get_run_checkpoints(self, run_id: str) -> List[WorkflowCheckpoint]:
        """Get all checkpoints for a run."""
        run = self.get_run(run_id)
        return run.checkpoints if run else []

    def should_retry_run(self, run_id: str) -> tuple[bool, Optional[WorkflowRun]]:
        """Check if a run should be retried based on error category."""
        run = self.get_run(run_id)
        if not run:
            return False, None

        if run.status != RunStatus.FAILED or not run.error_category:
            return False, run

        should_retry = self._retry_policy.should_retry(run.error_category, run.retry_count)
        return should_retry, run

    def create_retry_run(self, original_run_id: str) -> Optional[WorkflowRun]:
        """Create a retry run branched from the original."""
        original_run = self.get_run(original_run_id)
        if not original_run:
            return None

        retry_run = self.create_run(
            mode=original_run.mode,
            conversation_id=original_run.conversation_id,
            run_id=f"{original_run_id}_retry_{original_run.retry_count + 1}",
        )
        retry_run.parent_run_id = original_run_id
        retry_run.retry_count = original_run.retry_count + 1
        original_run.retry_count += 1

        # Initialize with same inputs to deterministic replay
        for checkpoint in original_run.checkpoints:
            retry_checkpoint = WorkflowCheckpoint(
                step_id=checkpoint.step_id,
                run_id=retry_run.run_id,
                agent=checkpoint.agent,
                inputs=checkpoint.inputs,
                depends_on=checkpoint.depends_on,
            )
            retry_run.checkpoints.append(retry_checkpoint)

        self._persist_run(retry_run)
        self._persist_run(original_run)
        self._append_event(
            original_run_id,
            WorkflowRunEventType.RUN_RETRIED,
            {
                "retry_run_id": retry_run.run_id,
                "retry_count": retry_run.retry_count,
                "fingerprint": original_run.error_fingerprint,
            },
        )
        logger.info(f"Created retry run {retry_run.run_id} from {original_run_id}")
        return retry_run

    def get_run_events(self, run_id: str) -> List[WorkflowRunEvent]:
        """Return the append-only event ledger for a run."""
        if run_id in self._event_cache:
            return self._event_cache[run_id]
        events = self._load_events(run_id)
        self._event_cache[run_id] = events
        return events

    def list_runs_by_conversation(self, conversation_id: str) -> List[WorkflowRun]:
        """List all runs for a conversation."""
        runs = []
        for run_file in self.storage_path.glob("*.json"):
            run = self._load_run(run_file.stem)
            if run and run.conversation_id == conversation_id:
                runs.append(run)
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    def _persist_run(self, run: WorkflowRun) -> None:
        """Persist run to storage."""
        try:
            run_file = self.storage_path / f"{run.run_id}.json"
            run_data = run.model_dump(mode="json", by_alias=False)  # Use model_dump for Pydantic v2
            run_file.write_text(json.dumps(run_data, indent=2, default=str))
        except Exception as exc:
            logger.error(f"Failed to persist run {run.run_id}: {exc}")

    def _load_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Load run from storage."""
        try:
            run_file = self.storage_path / f"{run_id}.json"
            if not run_file.exists():
                return None

            data = json.loads(run_file.read_text())
            # Parse nested checkpoints
            checkpoints = [WorkflowCheckpoint(**cp) for cp in data.get("checkpoints", [])]
            data["checkpoints"] = checkpoints
            # Parse datetime fields
            for field in ["created_at", "started_at", "completed_at"]:
                if field in data and isinstance(data[field], str):
                    data[field] = datetime.fromisoformat(data[field].replace("Z", "+00:00"))
            return WorkflowRun(**data)
        except Exception as exc:
            logger.error(f"Failed to load run {run_id}: {exc}")
            return None

    def _append_event(self, run_id: str, event_type: WorkflowRunEventType, data: Dict[str, object]) -> None:
        event = WorkflowRunEvent(
            event_id=uuid4().hex,
            run_id=run_id,
            event_type=event_type,
            data=data,
        )
        event_file = self.storage_path / f"{run_id}.events.jsonl"
        try:
            with event_file.open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception as exc:
            logger.error(f"Failed to append event for run {run_id}: {exc}")
            return
        self._event_cache.setdefault(run_id, []).append(event)

    def _load_events(self, run_id: str) -> List[WorkflowRunEvent]:
        event_file = self.storage_path / f"{run_id}.events.jsonl"
        if not event_file.exists():
            return []
        events: List[WorkflowRunEvent] = []
        try:
            with event_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    events.append(WorkflowRunEvent(**json.loads(line)))
        except Exception as exc:
            logger.error(f"Failed to load events for run {run_id}: {exc}")
            return []
        return events

    def _classify_error_category(self, error: Optional[str]) -> ErrorCategory:
        if not error:
            return ErrorCategory.UNKNOWN
        lowered = error.lower()
        transient_markers = ["timeout", "temporar", "connection", "rate limit", "unavailable", "reset"]
        permanent_markers = ["invalid", "not found", "unauthorized", "forbidden", "schema", "validation"]
        if any(marker in lowered for marker in transient_markers):
            return ErrorCategory.TRANSIENT
        if any(marker in lowered for marker in permanent_markers):
            return ErrorCategory.PERMANENT
        return ErrorCategory.UNKNOWN

    def _compute_error_fingerprint(self, error: Optional[str]) -> Optional[str]:
        if not error:
            return None
        lowered = error.lower()
        if "timeout" in lowered:
            return "timeout"
        if "rate" in lowered and "limit" in lowered:
            return "rate_limit"
        if "connection" in lowered or "socket" in lowered:
            return "connection"
        if "unauthorized" in lowered or "forbidden" in lowered:
            return "auth"
        if "validation" in lowered or "schema" in lowered:
            return "validation"
        return "unknown"
