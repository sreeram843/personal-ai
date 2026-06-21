from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings


class AuthError(Exception):
    """Raised when a JWT cannot be decoded or validated."""


def create_access_token(*, user_id: uuid.UUID, settings: Settings) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub")
        if not subject:
            raise AuthError("Token missing subject")
        return uuid.UUID(str(subject))
    except (InvalidTokenError, ValueError) as exc:
        raise AuthError("Invalid or expired token") from exc
