from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.workers import tasks

_settings = get_settings()


class WorkerSettings:
    functions = [tasks.ingest_documents_task, tasks.run_workflow_task, tasks.scheduled_reports_tick]
    cron_jobs = [
        cron(tasks.scheduled_reports_tick, minute={0, 15, 30, 45}, run_at_startup=False),
    ]
    max_jobs = 10
    job_timeout = 60 * 30
    keep_result = 3600
    redis_settings = RedisSettings.from_dsn(_settings.redis_url or "redis://127.0.0.1:6379/0")
