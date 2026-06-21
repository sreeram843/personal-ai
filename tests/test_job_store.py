"""Tests for background job store."""

from __future__ import annotations

from datetime import timezone

from app.schemas.jobs import BackgroundJobKind, BackgroundJobStatus
from app.services.job_store import JobStore


def test_job_store_create_and_update_in_memory() -> None:
    store = JobStore(redis_url=None)
    job = store.create_job(kind=BackgroundJobKind.INGEST, user_id="user-1")
    assert job.status == BackgroundJobStatus.QUEUED
    assert job.created_at.tzinfo == timezone.utc
    assert job.updated_at.tzinfo == timezone.utc

    updated = store.update_job(
        job.job_id,
        status=BackgroundJobStatus.COMPLETED,
        result={"count": 3},
    )
    assert updated is not None
    assert updated.status == BackgroundJobStatus.COMPLETED
    assert updated.result == {"count": 3}
    assert updated.updated_at.tzinfo == timezone.utc

    loaded = store.get_job(job.job_id)
    assert loaded is not None
    assert loaded.user_id == "user-1"
    assert loaded.kind == BackgroundJobKind.INGEST
