from __future__ import annotations

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

RUN_KEY_PREFIX = "personal-ai:run:"
RUN_EVENT_KEY_PREFIX = "personal-ai:run-events:"
DEFAULT_RUN_TTL_SECONDS = 60 * 60 * 24 * 14


class RunStore:
    """Stores and retrieves workflow runs with checkpoints."""

    def __init__(self, storage_path: str = "memory/runs") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, WorkflowRun] = {}
        self._event_cache: Dict[str, List[WorkflowRunEvent]] = {}
        self._retry_policy = RetryPolicy()

    def create_run(
        self,
        mode: str,
        conversation_id: Optional[str] = None,
        run_id: str | None = None,
        user_id: Optional[str] = None,
    ) -> WorkflowRun:
        if run_id is None:
            run_id = f"run_{datetime.utcnow().timestamp()}"

        run = WorkflowRun(
            run_id=run_id,
            mode=mode,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        self._cache[self._cache_key(run)] = run
        self._persist_run(run)
        self._append_event(
            run,
            WorkflowRunEventType.RUN_CREATED,
            {
                "mode": mode,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "status": run.status.value,
            },
        )
        logger.info("Created run %s for user %s", run_id, user_id)
        return run

    def get_run(self, run_id: str, *, user_id: Optional[str] = None) -> Optional[WorkflowRun]:
        if user_id is not None:
            cached = self._cache.get(self._cache_key_for(user_id, run_id))
            if cached:
                return cached
            run = self._load_run(self._run_file_for(user_id, run_id))
            if run is not None:
                self._cache[self._cache_key(run)] = run
            return run

        for run in self._iter_all_runs():
            if run.run_id == run_id:
                return run
        return None

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        error: Optional[str] = None,
        *,
        user_id: Optional[str] = None,
    ) -> Optional[WorkflowRun]:
        run = self.get_run(run_id, user_id=user_id)
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
            run,
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
        run = self.get_run(run_id)
        if not run:
            return None

        run.checkpoints.append(checkpoint)
        self._persist_run(run)
        self._append_event(
            run,
            WorkflowRunEventType.CHECKPOINT_ADDED,
            {
                "step_id": checkpoint.step_id,
                "agent": checkpoint.agent,
                "state": checkpoint.state.value,
                "depends_on": checkpoint.depends_on,
            },
        )
        return run

    def update_checkpoint(
        self,
        run_id: str,
        step_id: str,
        state: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[WorkflowCheckpoint]:
        run = self.get_run(run_id)
        if not run:
            return None

        checkpoint = next((item for item in run.checkpoints if item.step_id == step_id), None)
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
            run,
            WorkflowRunEventType.CHECKPOINT_UPDATED,
            {
                "step_id": checkpoint.step_id,
                "state": checkpoint.state.value,
                "error": checkpoint.error,
            },
        )
        return checkpoint

    def get_run_checkpoints(self, run_id: str) -> List[WorkflowCheckpoint]:
        run = self.get_run(run_id)
        return run.checkpoints if run else []

    def should_retry_run(self, run_id: str) -> tuple[bool, Optional[WorkflowRun]]:
        run = self.get_run(run_id)
        if not run:
            return False, None

        if run.status != RunStatus.FAILED or not run.error_category:
            return False, run

        should_retry = self._retry_policy.should_retry(run.error_category, run.retry_count)
        return should_retry, run

    def create_retry_run(self, original_run_id: str) -> Optional[WorkflowRun]:
        original_run = self.get_run(original_run_id)
        if not original_run:
            return None

        retry_run = self.create_run(
            mode=original_run.mode,
            conversation_id=original_run.conversation_id,
            run_id=f"{original_run_id}_retry_{original_run.retry_count + 1}",
            user_id=original_run.user_id,
        )
        retry_run.parent_run_id = original_run_id
        retry_run.retry_count = original_run.retry_count + 1
        original_run.retry_count += 1

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
            original_run,
            WorkflowRunEventType.RUN_RETRIED,
            {
                "retry_run_id": retry_run.run_id,
                "retry_count": retry_run.retry_count,
                "fingerprint": original_run.error_fingerprint,
            },
        )
        return retry_run

    def get_run_events(self, run_id: str, *, user_id: Optional[str] = None) -> List[WorkflowRunEvent]:
        run = self.get_run(run_id, user_id=user_id)
        if run is None:
            return []
        cache_key = self._cache_key(run)
        if cache_key in self._event_cache:
            return self._event_cache[cache_key]
        events = self._load_events(run)
        self._event_cache[cache_key] = events
        return events

    def list_runs_by_conversation(
        self,
        conversation_id: str,
        *,
        user_id: Optional[str] = None,
    ) -> List[WorkflowRun]:
        runs: List[WorkflowRun] = []
        for run in self._iter_all_runs(user_id=user_id):
            if run.conversation_id == conversation_id:
                runs.append(run)
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def attach_run_result(self, run_id: str, result: Dict[str, object]) -> Optional[WorkflowRun]:
        run = self.get_run(run_id)
        if not run:
            return None
        run.metadata["response"] = result
        self._persist_run(run)
        return run

    def _cache_key(self, run: WorkflowRun) -> str:
        return self._cache_key_for(run.user_id, run.run_id)

    @staticmethod
    def _cache_key_for(user_id: Optional[str], run_id: str) -> str:
        return f"{user_id or '_legacy'}:{run_id}"

    def _user_dir(self, user_id: Optional[str]) -> Path:
        path = self.storage_path / (user_id or "_legacy")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_file_for(self, user_id: Optional[str], run_id: str) -> Path:
        return self._user_dir(user_id) / f"{run_id}.json"

    def _run_file(self, run: WorkflowRun) -> Path:
        return self._run_file_for(run.user_id, run.run_id)

    def _event_file(self, run: WorkflowRun) -> Path:
        return self._user_dir(run.user_id) / f"{run.run_id}.events.jsonl"

    def _iter_all_runs(self, *, user_id: Optional[str] = None) -> List[WorkflowRun]:
        runs: List[WorkflowRun] = []
        dirs = [self._user_dir(user_id)] if user_id is not None else [
            path for path in self.storage_path.iterdir() if path.is_dir()
        ]
        for directory in dirs:
            for run_file in directory.glob("*.json"):
                if run_file.name.endswith(".events.json"):
                    continue
                run = self._load_run(run_file)
                if run is not None:
                    runs.append(run)
        return runs

    def _persist_run(self, run: WorkflowRun) -> None:
        try:
            run_file = self._run_file(run)
            run_data = run.model_dump(mode="json", by_alias=False)
            run_file.write_text(json.dumps(run_data, indent=2, default=str))
        except Exception as exc:
            logger.error("Failed to persist run %s: %s", run.run_id, exc)

    def _load_run(self, run_file: Path) -> Optional[WorkflowRun]:
        try:
            if not run_file.exists():
                return None
            data = json.loads(run_file.read_text())
            checkpoints = [WorkflowCheckpoint(**cp) for cp in data.get("checkpoints", [])]
            data["checkpoints"] = checkpoints
            for field in ["created_at", "started_at", "completed_at"]:
                if field in data and isinstance(data[field], str):
                    data[field] = datetime.fromisoformat(data[field].replace("Z", "+00:00"))
            return WorkflowRun(**data)
        except Exception as exc:
            logger.error("Failed to load run from %s: %s", run_file, exc)
            return None

    def _append_event(self, run: WorkflowRun, event_type: WorkflowRunEventType, data: Dict[str, object]) -> None:
        event = WorkflowRunEvent(
            event_id=uuid4().hex,
            run_id=run.run_id,
            event_type=event_type,
            data=data,
        )
        event_file = self._event_file(run)
        try:
            with event_file.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
        except Exception as exc:
            logger.error("Failed to append event for run %s: %s", run.run_id, exc)
            return
        self._event_cache.setdefault(self._cache_key(run), []).append(event)

    def _load_events(self, run: WorkflowRun) -> List[WorkflowRunEvent]:
        event_file = self._event_file(run)
        if not event_file.exists():
            return []
        events: List[WorkflowRunEvent] = []
        try:
            with event_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    events.append(WorkflowRunEvent(**json.loads(line)))
        except Exception as exc:
            logger.error("Failed to load events for run %s: %s", run.run_id, exc)
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


class RedisRunStore(RunStore):
    """Redis-backed workflow run store for multi-replica production deployments."""

    def __init__(self, redis_url: str, *, ttl_seconds: int = DEFAULT_RUN_TTL_SECONDS) -> None:
        super().__init__(storage_path="memory/runs")
        import redis

        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_seconds

    def _persist_run(self, run: WorkflowRun) -> None:
        key = f"{RUN_KEY_PREFIX}{self._cache_key(run)}"
        self._redis.setex(key, self._ttl_seconds, json.dumps(run.model_dump(mode="json"), default=str))

    def _load_run(self, run_file: Path) -> Optional[WorkflowRun]:
        return None

    def get_run(self, run_id: str, *, user_id: Optional[str] = None) -> Optional[WorkflowRun]:
        if user_id is not None:
            cached = self._cache.get(self._cache_key_for(user_id, run_id))
            if cached:
                return cached
            raw = self._redis.get(f"{RUN_KEY_PREFIX}{self._cache_key_for(user_id, run_id)}")
            if not raw:
                return None
            data = json.loads(raw)
            data["checkpoints"] = [WorkflowCheckpoint(**cp) for cp in data.get("checkpoints", [])]
            for field in ["created_at", "started_at", "completed_at"]:
                if field in data and isinstance(data[field], str):
                    data[field] = datetime.fromisoformat(data[field].replace("Z", "+00:00"))
            run = WorkflowRun(**data)
            self._cache[self._cache_key(run)] = run
            return run
        return super().get_run(run_id, user_id=user_id)

    def _append_event(self, run: WorkflowRun, event_type: WorkflowRunEventType, data: Dict[str, object]) -> None:
        event = WorkflowRunEvent(
            event_id=uuid4().hex,
            run_id=run.run_id,
            event_type=event_type,
            data=data,
        )
        key = f"{RUN_EVENT_KEY_PREFIX}{self._cache_key(run)}"
        self._redis.rpush(key, event.model_dump_json())
        self._redis.expire(key, self._ttl_seconds)
        self._event_cache.setdefault(self._cache_key(run), []).append(event)

    def _load_events(self, run: WorkflowRun) -> List[WorkflowRunEvent]:
        key = f"{RUN_EVENT_KEY_PREFIX}{self._cache_key(run)}"
        raw_events = self._redis.lrange(key, 0, -1)
        return [WorkflowRunEvent(**json.loads(item)) for item in raw_events]

    def _iter_all_runs(self, *, user_id: Optional[str] = None) -> List[WorkflowRun]:
        pattern = f"{RUN_KEY_PREFIX}{user_id or '*'}:*"
        runs: List[WorkflowRun] = []
        for key in self._redis.scan_iter(match=pattern):
            raw = self._redis.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            data["checkpoints"] = [WorkflowCheckpoint(**cp) for cp in data.get("checkpoints", [])]
            for field in ["created_at", "started_at", "completed_at"]:
                if field in data and isinstance(data[field], str):
                    data[field] = datetime.fromisoformat(data[field].replace("Z", "+00:00"))
            runs.append(WorkflowRun(**data))
        return runs


def build_run_store(*, storage_path: str, backend: str, redis_url: Optional[str]) -> RunStore:
    if backend == "redis" and redis_url:
        return RedisRunStore(redis_url)
    return RunStore(storage_path=storage_path)
