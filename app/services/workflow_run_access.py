from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.db.models import User
from app.services.conversation_store import get_conversation_for_user
from app.services.run_store import RunStore
from app.schemas.run import WorkflowRun


def verify_conversation_owned_by_user(
    db: Session,
    user: User,
    conversation_id: str | None,
) -> None:
    if not conversation_id:
        return
    try:
        conversation_uuid = uuid.UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation_id") from exc
    owned = get_conversation_for_user(db, user.id, conversation_uuid)
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


def require_workflow_run(
    run_store: RunStore,
    *,
    run_id: str,
    user: CurrentUser,
) -> WorkflowRun:
    run = run_store.get_run(run_id, user_id=str(user.id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")
    return run
