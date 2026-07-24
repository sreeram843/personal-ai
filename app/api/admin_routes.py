"""Platform admin API: users, invites, providers, routing, usage, signup mode."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.core.auth import AdminUser, StaffUser, create_invite
from app.core.config import Settings, get_settings
from app.core.deps import get_llm_gateway, get_workflow_model_profile
from app.db.models import Conversation, LlmProvider, LlmRouting, LlmUsageEvent, User, UserInvite, UserRole
from app.db.session import get_db
from app.schemas.admin import (
    AdminUserSummary,
    AdminUserUpdate,
    InviteCreate,
    InviteResponse,
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
    RoutingResponse,
    RoutingUpdate,
    SignupModeResponse,
    SignupModeUpdate,
    UsageByUserRow,
    UsagePoint,
    UsageSummaryResponse,
)
from app.services.secret_box import encrypt_secret, key_last4
from app.services.audit_log import record_audit
from app.services.settings_store import (
    clear_settings_cache,
    get_signup_mode,
    set_signup_mode,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _provider_response(row: LlmProvider) -> ProviderResponse:
    return ProviderResponse(
        id=str(row.id),
        name=row.name,
        display_name=row.display_name,
        base_url=row.base_url,
        enabled=row.enabled,
        has_key=bool(row.encrypted_api_key),
        key_last4=row.key_last4,
    )


def _invalidate_llm_runtime() -> None:
    clear_settings_cache()
    get_llm_gateway.cache_clear()
    get_workflow_model_profile.cache_clear()


@router.get("/me")
def admin_me(user: StaffUser) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_admin": user.is_admin,
    }


@router.get("/users", response_model=List[AdminUserSummary])
def list_users(
    user: StaffUser,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(default=None),
) -> List[AdminUserSummary]:
    stmt = select(User).order_by(User.created_at.desc())
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like))
    users = list(db.scalars(stmt).all())
    out: List[AdminUserSummary] = []
    for item in users:
        conv_count = db.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == item.id)
        ) or 0
        prompt = db.scalar(
            select(func.coalesce(func.sum(LlmUsageEvent.prompt_tokens), 0)).where(LlmUsageEvent.user_id == item.id)
        ) or 0
        completion = db.scalar(
            select(func.coalesce(func.sum(LlmUsageEvent.completion_tokens), 0)).where(
                LlmUsageEvent.user_id == item.id
            )
        ) or 0
        out.append(
            AdminUserSummary(
                id=str(item.id),
                email=item.email,
                display_name=item.display_name,
                role=item.role,
                is_active=item.is_active,
                created_at=item.created_at,
                last_login_at=item.last_login_at,
                conversation_count=int(conv_count),
                prompt_tokens=int(prompt),
                completion_tokens=int(completion),
                total_tokens=int(prompt) + int(completion),
            )
        )
    return out


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    actor: StaffUser,
    db: Session = Depends(get_db),
) -> AdminUserSummary:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role is not None:
        if not actor.is_admin:
            raise HTTPException(status_code=403, detail="Only admins can change roles")
        if body.role not in {UserRole.user.value, UserRole.support.value, UserRole.admin.value}:
            raise HTTPException(status_code=400, detail="Invalid role")
        target.role = body.role

    if body.is_active is not None:
        if target.is_admin and not actor.is_admin:
            raise HTTPException(status_code=403, detail="Support cannot disable admins")
        target.is_active = body.is_active

    db.commit()
    db.refresh(target)
    record_audit(
        "admin.user.update",
        user_id=str(actor.id),
        detail={
            "target_user_id": str(target.id),
            "role": target.role,
            "is_active": target.is_active,
        },
    )
    return AdminUserSummary(
        id=str(target.id),
        email=target.email,
        display_name=target.display_name,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        last_login_at=target.last_login_at,
    )


@router.get("/invites", response_model=List[InviteResponse])
def list_invites(user: StaffUser, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> List[InviteResponse]:
    rows = list(db.scalars(select(UserInvite).order_by(UserInvite.created_at.desc())).all())
    base = (settings.demo_full_app_url or "").rstrip("/") or "https://app.cura-i.com"
    return [
        InviteResponse(
            id=str(row.id),
            email=row.email,
            role=row.role,
            token=row.token,
            expires_at=row.expires_at,
            accepted_at=row.accepted_at,
            invite_url=f"{base}/login?invite={row.token}",
        )
        for row in rows
    ]


@router.post("/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_user_invite(
    body: InviteCreate,
    user: StaffUser,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InviteResponse:
    if body.role == UserRole.admin.value and not user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can invite admins")
    try:
        invite = create_invite(
            db,
            email=str(body.email),
            role=body.role,
            created_by=user.id,
            expires_days=body.expires_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        "admin.invite.create",
        user_id=str(user.id),
        detail={"email": invite.email, "role": invite.role},
    )
    base = (settings.demo_full_app_url or "").rstrip("/") or "https://app.cura-i.com"
    return InviteResponse(
        id=str(invite.id),
        email=invite.email,
        role=invite.role,
        token=invite.token,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        invite_url=f"{base}/login?invite={invite.token}",
    )


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def revoke_invite(invite_id: uuid.UUID, user: StaffUser, db: Session = Depends(get_db)) -> Response:
    invite = db.get(UserInvite, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    db.delete(invite)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/providers", response_model=List[ProviderResponse])
def list_providers(user: AdminUser, db: Session = Depends(get_db)) -> List[ProviderResponse]:
    rows = list(db.scalars(select(LlmProvider).order_by(LlmProvider.created_at.asc())).all())
    return [_provider_response(row) for row in rows]


@router.post("/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(
    body: ProviderCreate,
    user: AdminUser,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProviderResponse:
    name = body.name.strip().lower().replace(" ", "_")
    existing = db.scalar(select(LlmProvider).where(LlmProvider.name == name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Provider name already exists")
    encrypted = None
    last4 = None
    if body.api_key and body.api_key.strip():
        encrypted = encrypt_secret(body.api_key.strip(), settings)
        last4 = key_last4(body.api_key.strip())
    row = LlmProvider(
        name=name,
        display_name=body.display_name.strip(),
        base_url=body.base_url.strip().rstrip("/"),
        encrypted_api_key=encrypted,
        key_last4=last4,
        enabled=body.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _invalidate_llm_runtime()
    return _provider_response(row)


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdate,
    user: AdminUser,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProviderResponse:
    row = db.get(LlmProvider, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if body.display_name is not None:
        row.display_name = body.display_name.strip()
    if body.base_url is not None:
        row.base_url = body.base_url.strip().rstrip("/")
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.api_key is not None and body.api_key.strip():
        row.encrypted_api_key = encrypt_secret(body.api_key.strip(), settings)
        row.key_last4 = key_last4(body.api_key.strip())
    db.commit()
    db.refresh(row)
    _invalidate_llm_runtime()
    return _provider_response(row)


@router.get("/routing", response_model=RoutingResponse)
def get_routing(user: AdminUser, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> RoutingResponse:
    from app.services.settings_store import get_effective_routing

    routing = get_effective_routing(db, settings)
    return RoutingResponse(**routing.__dict__)


_BUILTIN_PROVIDERS = frozenset({"ollama", "openai"})


def _assert_routing_providers(body: RoutingUpdate, db: Session) -> None:
    enabled = {
        name
        for name in db.scalars(select(LlmProvider.name).where(LlmProvider.enabled.is_(True))).all()
    }
    allowed = enabled | _BUILTIN_PROVIDERS
    fields = (
        ("default_provider", body.default_provider),
        ("planner_provider", body.planner_provider),
        ("synthesizer_provider", body.synthesizer_provider),
        ("reviewer_provider", body.reviewer_provider),
        ("writer_provider", body.writer_provider),
    )
    for field, value in fields:
        name = value.strip().lower()
        if name not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown provider '{value}' for {field}. "
                    "Add and enable it under Providers first (or use ollama/openai)."
                ),
            )


@router.put("/routing", response_model=RoutingResponse)
def put_routing(body: RoutingUpdate, user: AdminUser, db: Session = Depends(get_db)) -> RoutingResponse:
    _assert_routing_providers(body, db)
    row = db.scalar(select(LlmRouting).order_by(LlmRouting.id.asc()).limit(1))
    if row is None:
        row = LlmRouting()
        db.add(row)
    payload = body.model_dump()
    for field, value in payload.items():
        if field.endswith("_provider"):
            value = str(value).strip().lower()
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    _invalidate_llm_runtime()
    return RoutingResponse(
        default_provider=row.default_provider,
        default_model=row.default_model,
        planner_provider=row.planner_provider,
        planner_model=row.planner_model,
        synthesizer_provider=row.synthesizer_provider,
        synthesizer_model=row.synthesizer_model,
        reviewer_provider=row.reviewer_provider,
        reviewer_model=row.reviewer_model,
        writer_provider=row.writer_provider,
        writer_model=row.writer_model,
    )


@router.get("/signup-mode", response_model=SignupModeResponse)
def read_signup_mode(user: AdminUser, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> SignupModeResponse:
    return SignupModeResponse(mode=get_signup_mode(db, settings))


@router.put("/signup-mode", response_model=SignupModeResponse)
def write_signup_mode(body: SignupModeUpdate, user: AdminUser, db: Session = Depends(get_db)) -> SignupModeResponse:
    return SignupModeResponse(mode=set_signup_mode(db, body.mode))


def _parse_range(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(1, min(days, 365)))
    return start, end


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def usage_summary(
    user: StaffUser,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> UsageSummaryResponse:
    start, end = _parse_range(days)
    day_col = cast(LlmUsageEvent.created_at, Date).label("day")
    rows = list(
        db.execute(
            select(
                day_col,
                func.coalesce(func.sum(LlmUsageEvent.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsageEvent.completion_tokens), 0),
                func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0),
            )
            .where(LlmUsageEvent.created_at >= start)
            .where(LlmUsageEvent.created_at <= end)
            .group_by(day_col)
            .order_by(day_col)
        ).all()
    )
    series = [
        UsagePoint(
            date=row[0].date().isoformat() if hasattr(row[0], "date") else str(row[0])[:10],
            prompt_tokens=int(row[1]),
            completion_tokens=int(row[2]),
            total_tokens=int(row[3]),
        )
        for row in rows
    ]
    prompt_total = sum(p.prompt_tokens for p in series)
    completion_total = sum(p.completion_tokens for p in series)
    by_model_rows = list(
        db.execute(
            select(
                LlmUsageEvent.model,
                func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0),
            )
            .where(LlmUsageEvent.created_at >= start)
            .where(LlmUsageEvent.created_at <= end)
            .group_by(LlmUsageEvent.model)
            .order_by(func.sum(LlmUsageEvent.total_tokens).desc())
        ).all()
    )
    return UsageSummaryResponse(
        prompt_tokens=prompt_total,
        completion_tokens=completion_total,
        total_tokens=prompt_total + completion_total,
        series=series,
        by_model=[{"model": r[0], "total_tokens": int(r[1])} for r in by_model_rows],
    )


@router.get("/usage/by-user", response_model=List[UsageByUserRow])
def usage_by_user(
    user: StaffUser,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> List[UsageByUserRow]:
    start, end = _parse_range(days)
    rows = list(
        db.execute(
            select(
                LlmUsageEvent.user_id,
                User.email,
                User.display_name,
                func.coalesce(func.sum(LlmUsageEvent.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsageEvent.completion_tokens), 0),
                func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0),
            )
            .outerjoin(User, User.id == LlmUsageEvent.user_id)
            .where(LlmUsageEvent.created_at >= start)
            .where(LlmUsageEvent.created_at <= end)
            .group_by(LlmUsageEvent.user_id, User.email, User.display_name)
            .order_by(func.sum(LlmUsageEvent.total_tokens).desc())
        ).all()
    )
    return [
        UsageByUserRow(
            user_id=str(r[0]) if r[0] else None,
            email=r[1],
            display_name=r[2],
            prompt_tokens=int(r[3]),
            completion_tokens=int(r[4]),
            total_tokens=int(r[5]),
        )
        for r in rows
    ]


__all__ = ["router"]
