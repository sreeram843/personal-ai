from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.auth import CurrentUser
from app.core.deps import get_schedule_store
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleListResponse,
    ScheduledReportResponse,
)
from app.services.schedule_store import ScheduleStore

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _to_response(item) -> ScheduledReportResponse:
    return ScheduledReportResponse(
        id=item.id,
        title=item.title,
        prompt=item.prompt,
        interval_minutes=item.interval_minutes,
        enabled=item.enabled,
        last_run_at=item.last_run_at,
        next_run_at=item.next_run_at,
        last_run_id=item.last_run_id,
    )


@router.get("", response_model=ScheduleListResponse)
def list_schedules(
    user: CurrentUser,
    store: ScheduleStore = Depends(get_schedule_store),
) -> ScheduleListResponse:
    items = store.list_for_user(str(user.id))
    return ScheduleListResponse(schedules=[_to_response(item) for item in items])


@router.post("", response_model=ScheduledReportResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreateRequest,
    user: CurrentUser,
    store: ScheduleStore = Depends(get_schedule_store),
) -> ScheduledReportResponse:
    created = store.create(
        user_id=str(user.id),
        title=payload.title,
        prompt=payload.prompt,
        interval_minutes=payload.interval_minutes,
    )
    return _to_response(created)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_schedule(
    schedule_id: str,
    user: CurrentUser,
    store: ScheduleStore = Depends(get_schedule_store),
) -> Response:
    if not store.delete(user_id=str(user.id), schedule_id=schedule_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
