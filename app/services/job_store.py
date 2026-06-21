from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.schemas.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "personal-ai:job:"
DEFAULT_JOB_TTL_SECONDS = 60 * 60 * 24 * 7


class JobStore:
    """Persist background job status in Redis or in-memory storage."""

    def __init__(self, redis_url: Optional[str] = None, ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._memory: Dict[str, str] = {}
        self._redis = None
        if redis_url:
            import redis

            self._redis = redis.from_url(redis_url, decode_responses=True)

    def create_job(
        self,
        *,
        kind: BackgroundJobKind,
        user_id: str,
        run_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> BackgroundJob:
        job = BackgroundJob(
            job_id=job_id or uuid4().hex,
            kind=kind,
            user_id=user_id,
            run_id=run_id,
        )
        self._write(job)
        return job

    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        raw = self._read(job_id)
        if not raw:
            return None
        return BackgroundJob(**json.loads(raw))

    def update_job(
        self,
        job_id: str,
        *,
        status: BackgroundJobStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[BackgroundJob]:
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        self._write(job)
        return job

    def _key(self, job_id: str) -> str:
        return f"{JOB_KEY_PREFIX}{job_id}"

    def _write(self, job: BackgroundJob) -> None:
        payload = job.model_dump(mode="json")
        encoded = json.dumps(payload, default=str)
        key = self._key(job.job_id)
        if self._redis is not None:
            self._redis.setex(key, self._ttl_seconds, encoded)
            return
        self._memory[key] = encoded

    def _read(self, job_id: str) -> Optional[str]:
        key = self._key(job_id)
        if self._redis is not None:
            return self._redis.get(key)
        return self._memory.get(key)
