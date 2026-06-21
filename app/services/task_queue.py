from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Protocol

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest
from app.schemas.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from app.services.job_store import JobStore

logger = logging.getLogger(__name__)


class TaskQueue(Protocol):
    async def enqueue_ingest(
        self,
        *,
        job: BackgroundJob,
        documents: list[dict[str, Any]],
    ) -> None:
        ...

    async def enqueue_workflow(
        self,
        *,
        run_id: str,
        user_id: str,
        payload: Dict[str, Any],
        job: Optional[BackgroundJob] = None,
    ) -> None:
        ...


class DisabledTaskQueue:
    async def enqueue_ingest(self, *, job: BackgroundJob, documents: list[dict[str, Any]]) -> None:
        raise RuntimeError("Background workers are disabled")

    async def enqueue_workflow(
        self,
        *,
        run_id: str,
        user_id: str,
        payload: Dict[str, Any],
        job: Optional[BackgroundJob] = None,
    ) -> None:
        raise RuntimeError("Background workers are disabled")


class InlineTaskQueue:
    """Execute worker tasks synchronously in-process (tests and local fallback)."""

    def __init__(self, ctx: Optional[dict] = None) -> None:
        self._ctx = ctx or {}

    def _base_ctx(self) -> dict:
        return {"job_store": _job_store_for_inline(), **self._ctx}

    async def enqueue_ingest(self, *, job: BackgroundJob, documents: list[dict[str, Any]]) -> None:
        from app.workers.tasks import ingest_documents_task

        await ingest_documents_task(self._base_ctx(), job.job_id, job.user_id, documents)

    async def enqueue_workflow(
        self,
        *,
        run_id: str,
        user_id: str,
        payload: Dict[str, Any],
        job: Optional[BackgroundJob] = None,
    ) -> None:
        from app.workers.tasks import run_workflow_task

        await run_workflow_task(
            self._base_ctx(),
            run_id,
            user_id,
            payload,
            job.job_id if job else None,
        )


def _job_store_for_inline() -> JobStore:
    from app.core.deps import get_job_store

    return get_job_store()


class ArqTaskQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            from arq import create_pool
            from arq.connections import RedisSettings

            self._pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
        return self._pool

    async def enqueue_ingest(self, *, job: BackgroundJob, documents: list[dict[str, Any]]) -> None:
        pool = await self._get_pool()
        await pool.enqueue_job("ingest_documents_task", job.job_id, job.user_id, documents)

    async def enqueue_workflow(
        self,
        *,
        run_id: str,
        user_id: str,
        payload: Dict[str, Any],
        job: Optional[BackgroundJob] = None,
    ) -> None:
        pool = await self._get_pool()
        await pool.enqueue_job(
            "run_workflow_task",
            run_id,
            user_id,
            payload,
            job.job_id if job else None,
        )


def build_task_queue(settings: Settings, job_store: JobStore) -> TaskQueue:
    if not settings.enable_background_workers:
        return DisabledTaskQueue()
    if settings.worker_queue_backend == "inline":
        return InlineTaskQueue()
    if not settings.redis_url:
        logger.warning("Background workers enabled but REDIS_URL is unset; using inline queue")
        return InlineTaskQueue()
    return ArqTaskQueue(settings.redis_url)


_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    global _task_queue
    if _task_queue is None:
        settings = get_settings()
        from app.core.deps import get_job_store

        _task_queue = build_task_queue(settings, get_job_store())
    return _task_queue


def reset_task_queue() -> None:
    global _task_queue
    _task_queue = None
