from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import AuthError, decode_access_token
from app.db.models import User
from app.db.session import get_db

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _parse_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def ensure_dev_user(db: Session, settings: Settings) -> User:
    user = db.get(User, DEV_USER_ID)
    if user is not None:
        return user

    user = User(
        id=DEV_USER_ID,
        email=settings.dev_user_email,
        display_name=settings.dev_user_display_name,
        external_id="dev-user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_user_by_google(
    db: Session,
    *,
    sub: str,
    email: Optional[str],
    display_name: Optional[str],
) -> User:
    """Find or create a user from Google OAuth subject and profile claims."""
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
        if changed:
            db.commit()
            db.refresh(existing)
        return existing

    if email:
        by_email = get_user_by_email(db, email)
        if by_email is not None:
            by_email.external_id = normalized_sub
            if display_name:
                by_email.display_name = display_name
            db.commit()
            db.refresh(by_email)
            return by_email

    normalized_email = email.strip().lower() if email else None
    fallback_name = display_name or (normalized_email.split("@", 1)[0] if normalized_email else "User")
    user = User(
        external_id=normalized_sub,
        email=normalized_email,
        display_name=fallback_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

__all__ = [
    "CurrentUser",
    "DEV_USER_ID",
    "ensure_dev_user",
    "get_current_user",
    "get_or_create_user_by_email",
    "get_or_create_user_by_google",
    "get_user_by_email",
]
