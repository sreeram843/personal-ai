from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import AuthError, decode_access_token
from app.db.models import User, UserInvite, UserRole
from app.db.session import get_db
from app.services.settings_store import get_signup_mode

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _parse_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def parse_admin_emails(settings: Settings) -> set[str]:
    return {
        part.strip().lower()
        for part in (settings.admin_emails or "").split(",")
        if part.strip()
    }


def apply_admin_bootstrap(user: User, settings: Settings, db: Session) -> User:
    emails = parse_admin_emails(settings)
    if user.email and user.email.lower() in emails and user.role != UserRole.admin.value:
        user.role = UserRole.admin.value
        db.commit()
        db.refresh(user)
    return user


def ensure_dev_user(db: Session, settings: Settings) -> User:
    user = db.get(User, DEV_USER_ID)
    if user is not None:
        if user.role != UserRole.admin.value:
            user.role = UserRole.admin.value
            db.commit()
            db.refresh(user)
        return apply_admin_bootstrap(user, settings, db)

    user = User(
        id=DEV_USER_ID,
        email=settings.dev_user_email,
        display_name=settings.dev_user_display_name,
        external_id="dev-user",
        role=UserRole.admin.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return apply_admin_bootstrap(user, settings, db)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    normalized = email.strip().lower()
    if not normalized:
        return None
    return db.scalar(select(User).where(User.email == normalized))


def get_or_create_user_by_email(db: Session, email: str) -> User:
    existing = get_user_by_email(db, email)
    if existing is not None:
        return existing

    normalized = email.strip().lower()
    user = User(
        email=normalized,
        display_name=normalized.split("@", 1)[0],
        role=UserRole.user.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _consume_invite_for_email(db: Session, email: str) -> Optional[UserInvite]:
    normalized = email.strip().lower()
    now = datetime.now(timezone.utc)
    invite = db.scalar(
        select(UserInvite)
        .where(UserInvite.email == normalized)
        .where(UserInvite.accepted_at.is_(None))
        .where(UserInvite.expires_at > now)
        .order_by(UserInvite.created_at.desc())
    )
    if invite is None:
        return None
    invite.accepted_at = now
    db.commit()
    db.refresh(invite)
    return invite


def get_or_create_user_by_google(
    db: Session,
    *,
    sub: str,
    email: Optional[str],
    display_name: Optional[str],
    settings: Optional[Settings] = None,
) -> User:
    """Find or create a user from Google OAuth subject and profile claims."""
    cfg = settings or get_settings()
    normalized_sub = sub.strip()
    if not normalized_sub:
        raise ValueError("Google subject is required")

    existing = db.scalar(select(User).where(User.external_id == normalized_sub))
    if existing is not None:
        changed = False
        if email:
            normalized_email = email.strip().lower()
            if existing.email != normalized_email:
                existing.email = normalized_email
                changed = True
        if display_name and existing.display_name != display_name:
            existing.display_name = display_name
            changed = True
        existing.last_login_at = datetime.now(timezone.utc)
        changed = True
        if changed:
            db.commit()
            db.refresh(existing)
        return apply_admin_bootstrap(existing, cfg, db)

    if email:
        by_email = get_user_by_email(db, email)
        if by_email is not None:
            by_email.external_id = normalized_sub
            if display_name:
                by_email.display_name = display_name
            by_email.last_login_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(by_email)
            return apply_admin_bootstrap(by_email, cfg, db)

    signup_mode = get_signup_mode(db, cfg)
    invite: Optional[UserInvite] = None
    if signup_mode == "invite":
        if not email:
            raise PermissionError("An invite email is required to join this instance")
        invite = _consume_invite_for_email(db, email)
        admin_emails = parse_admin_emails(cfg)
        if invite is None and email.strip().lower() not in admin_emails:
            raise PermissionError("Sign-up is invite-only. Ask an admin for an invite.")

    normalized_email = email.strip().lower() if email else None
    fallback_name = display_name or (normalized_email.split("@", 1)[0] if normalized_email else "User")
    role = invite.role if invite is not None else UserRole.user.value
    if normalized_email and normalized_email in parse_admin_emails(cfg):
        role = UserRole.admin.value

    user = User(
        external_id=normalized_sub,
        email=normalized_email,
        display_name=fallback_name,
        role=role,
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return apply_admin_bootstrap(user, cfg, db)


def create_invite(
    db: Session,
    *,
    email: str,
    role: str = UserRole.user.value,
    created_by: Optional[uuid.UUID] = None,
    expires_days: int = 14,
) -> UserInvite:
    if role not in {UserRole.user.value, UserRole.support.value, UserRole.admin.value}:
        raise ValueError("Invalid role")
    invite = UserInvite(
        email=email.strip().lower(),
        token=secrets.token_urlsafe(32),
        role=role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_days),
        created_by=created_by,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def get_current_user(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: Annotated[Optional[str], Header()] = None,
) -> User:
    """Resolve the authenticated user from JWT or dev bypass."""
    if settings.auth_disabled:
        return ensure_dev_user(db, settings)

    token = _parse_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = decode_access_token(token, settings)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return apply_admin_bootstrap(user, settings, db)


def require_staff(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
StaffUser = Annotated[User, Depends(require_staff)]
AdminUser = Annotated[User, Depends(require_admin)]

__all__ = [
    "AdminUser",
    "CurrentUser",
    "DEV_USER_ID",
    "StaffUser",
    "apply_admin_bootstrap",
    "create_invite",
    "ensure_dev_user",
    "get_current_user",
    "get_or_create_user_by_email",
    "get_or_create_user_by_google",
    "get_user_by_email",
    "parse_admin_emails",
    "require_admin",
    "require_staff",
]
