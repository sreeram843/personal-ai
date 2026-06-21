from __future__ import annotations

from typing import Any


class GoogleAuthError(Exception):
    """Raised when a Google ID token cannot be verified."""


def verify_google_id_token(token: str, client_id: str) -> dict[str, Any]:
    """Verify a Google Sign-In ID token and return its claims."""
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
    except ImportError as exc:  # pragma: no cover
        raise GoogleAuthError("Google auth dependencies are not installed") from exc

    try:
        claims = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
    except ValueError as exc:
        raise GoogleAuthError(str(exc)) from exc

    if not isinstance(claims, dict):
        raise GoogleAuthError("Invalid Google token payload")

    return claims


__all__ = ["GoogleAuthError", "verify_google_id_token"]
