from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class TokenRequest(BaseModel):
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email for token issuance when AUTH_DISABLED=false",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class UserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True

    @classmethod
    def from_db(cls, user) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=getattr(user, "role", None) or "user",
            is_active=bool(getattr(user, "is_active", True)),
        )


class AuthConfigResponse(BaseModel):
    auth_disabled: bool
    google_client_id: Optional[str] = None
    google_auth_enabled: bool = False
    signup_mode: str = "invite"
    privacy_policy_url: Optional[str] = None
    terms_of_service_url: Optional[str] = None
    support_email: Optional[str] = None


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(min_length=10, description="Google Sign-In ID token")


__all__ = [
    "AuthConfigResponse",
    "GoogleAuthRequest",
    "TokenRequest",
    "TokenResponse",
    "UserResponse",
]
