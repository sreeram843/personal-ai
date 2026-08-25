from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.schemas.chat import ChatRequest
from app.schemas.documents import IngestDocument
from app.schemas.jobs import BackgroundJobStatus
from app.schemas.run import RunStatus
from app.services.ingest_service import ingest_documents_for_user_id
from app.services.job_store import JobStore
from app.services.orchestrated_runner import run_orchestrated_mode
from app.services.run_store import RunStore

logger = logging.getLogger(__name__)


def _job_store_from_ctx(ctx: dict) -> JobStore:
    store = ctx.get("job_store")
    if store is not None:
        return store
    from app.core.deps import get_job_store

    return get_job_store()


async def ingest_documents_task(
    ctx: dict,
    job_id: str,
    user_id: str,
    documents: list[dict[str, Any]],
) -> int:
    settings = get_settings()
    job_store = _job_store_from_ctx(ctx)
    job_store.update_job(job_id, status=BackgroundJobStatus.IN_PROGRESS)

    session_factory = get_session_factory()
    db = session_factory()
    overrides = ctx.get("service_overrides", {})
    try:
        parsed = [IngestDocument(**document) for document in documents]
        count = await ingest_documents_for_user_id(
            db=db,
            user_id=UUID(user_id),
            documents=parsed,
            settings=settings,
            ollama=overrides.get("ollama"),
            vector_store=overrides.get("vector_store"),
        )
        job_store.update_job(job_id, status=BackgroundJobStatus.COMPLETED, result={"count": count})
        return count
    except Exception as exc:
        logger.exception("Ingest job %s failed", job_id)
        job_store.update_job(job_id, status=BackgroundJobStatus.FAILED, error=str(exc))
        raise
    finally:
        db.close()


async def run_workflow_task(
    ctx: dict,
    run_id: str,
    user_id: str,
    payload: Dict[str, Any],
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    job_store = _job_store_from_ctx(ctx)
    if job_id:
        job_store.update_job(job_id, status=BackgroundJobStatus.IN_PROGRESS)

    from app.core.deps import (
        get_llm_gateway,
        get_ollama_client,
        get_run_store,
        get_tool_registry,
        get_vector_store,
        get_web_search,
        get_workflow_memory_store,
        get_workflow_model_profile,
    )

    run_store = get_run_store()
    run_store.update_run_status(run_id, RunStatus.IN_PROGRESS)

    try:
        request = ChatRequest(**payload)
        response = await run_orchestrated_mode(
            mode="workflow",
            payload=request,
            user_id=user_id,
            ollama=get_ollama_client(),
            llm_gateway=get_llm_gateway(),
            model_profile=get_workflow_model_profile(),
            vector_store=get_vector_store(),
            web_search=get_web_search(),
            workflow_memory=get_workflow_memory_store(),
            tool_registry=get_tool_registry(),
        )
        if response.workflow:
            response.workflow.run_id = run_id
        result = response.model_dump(mode="json")
        run_store.attach_run_result(run_id, result)
        run_store.update_run_status(run_id, RunStatus.COMPLETED)
        if job_id:
            job_store.update_job(job_id, status=BackgroundJobStatus.COMPLETED, result={"run_id": run_id})
        return result
    except Exception as exc:
        logger.exception("Workflow job %s failed", run_id)
        run_store.update_run_status(run_id, RunStatus.FAILED, error=str(exc))
        if job_id:
            job_store.update_job(job_id, status=BackgroundJobStatus.FAILED, error=str(exc))
        raise


async def scheduled_reports_tick(ctx: dict) -> Dict[str, Any]:
    """ARQ cron hook: enqueue due scheduled workflow reports."""
    settings = get_settings()
    if not settings.enable_background_workers:
        return {"skipped": True, "processed": 0, "suppressed": 0}

    from app.core.deps import get_run_store, get_schedule_store
    from app.services.alert_governance import (
        AlertGovernance,
        condition_key,
        schedule_tier,
    )
    from app.services.task_queue import get_task_queue

    store = get_schedule_store()
    due = store.list_due()
    if not due:
        return {"processed": 0, "suppressed": 0}

    governance = AlertGovernance(
        file_path=settings.alert_governance_path,
        refractory_minutes=settings.alert_refractory_minutes,
    )
    run_store = get_run_store()
    task_queue = get_task_queue()
    processed = 0
    for schedule in due:
        key = condition_key(
            user_id=schedule.user_id,
            schedule_id=schedule.id,
            prompt=schedule.prompt,
        )
        tier = schedule_tier(schedule)
        if not governance.should_notify(key, tier=tier):
            # Advance next_run_at so a suppressed item does not stay due forever.
            store.mark_run(schedule.id, run_id=schedule.last_run_id or "suppressed")
            processed += 1
            continue
        run = run_store.create_run(mode="workflow", conversation_id=None, user_id=schedule.user_id)
        payload = {
            "message": schedule.prompt,
            "workflow": {
                "enabled": True,
                "use_rag": True,
                "include_trace": True,
                "persist_memory": True,
                "max_steps": 6,
            },
        }
        try:
            await task_queue.enqueue_workflow(
                run_id=run.run_id,
                user_id=schedule.user_id,
                payload=payload,
            )
            governance.record_fire(key, tier=tier)
            store.mark_run(schedule.id, run_id=run.run_id)
            processed += 1
        except Exception:
            logger.exception("Scheduled report %s failed to enqueue", schedule.id)
    return {"processed": processed, "suppressed": governance.suppressed}
