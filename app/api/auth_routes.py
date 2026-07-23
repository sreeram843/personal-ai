from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import (
    CurrentUser,
    ensure_dev_user,
    get_or_create_user_by_google,
)
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import (
    AuthConfigResponse,
    GoogleAuthRequest,
    TokenRequest,
    TokenResponse,
    UserResponse,
)
from app.services.google_auth import GoogleAuthError, verify_google_id_token
from app.services.settings_store import get_signup_mode

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigResponse)
def read_auth_config(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthConfigResponse:
    """Public auth configuration for the frontend login flow."""
    google_client_id = (settings.google_client_id or "").strip() or None
    return AuthConfigResponse(
        auth_disabled=settings.auth_disabled,
        google_client_id=google_client_id,
        google_auth_enabled=not settings.auth_disabled and google_client_id is not None,
        signup_mode=get_signup_mode(db, settings),
    )


@router.post("/token", response_model=TokenResponse)
def issue_token(
    body: TokenRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Issue a JWT for API access. Open email minting is disabled when auth is on."""
    if settings.auth_disabled:
        user = ensure_dev_user(db, settings)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email token minting is disabled. Use Google sign-in or an invite.",
        )

    token = create_access_token(user_id=user.id, settings=settings)
    return TokenResponse(access_token=token, user_id=str(user.id))


@router.post("/google", response_model=TokenResponse)
def google_sign_in(
    body: GoogleAuthRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Exchange a Google ID token for an application JWT."""
    if settings.auth_disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google sign-in is disabled while AUTH_DISABLED=true",
        )

    client_id = (settings.google_client_id or "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )

    try:
        claims = verify_google_id_token(body.id_token, client_id)
    except GoogleAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    sub = str(claims.get("sub") or "").strip()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token is missing subject",
        )

    email = claims.get("email")
    display_name = claims.get("name")
    try:
        user = get_or_create_user_by_google(
            db,
            sub=sub,
            email=str(email).strip() if email else None,
            display_name=str(display_name).strip() if display_name else None,
            settings=settings,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    token = create_access_token(user_id=user.id, settings=settings)
    return TokenResponse(access_token=token, user_id=str(user.id))


@router.get("/me", response_model=UserResponse)
def read_current_user(user: CurrentUser) -> UserResponse:
    """Return the authenticated user (requires Bearer token when AUTH_DISABLED=false)."""
    return UserResponse.from_db(user)
