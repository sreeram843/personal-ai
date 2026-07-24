from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class AdminUserSummary(BaseModel):
    id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    conversation_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = "user"
    expires_days: int = Field(default=14, ge=1, le=90)


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    token: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    invite_url: Optional[str] = None


class ProviderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=8, max_length=512)
    api_key: Optional[str] = None
    enabled: bool = True


class ProviderUpdate(BaseModel):
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None


class ProviderResponse(BaseModel):
    id: str
    name: str
    display_name: str
    base_url: str
    enabled: bool
    has_key: bool
    key_last4: Optional[str] = None


class RoutingUpdate(BaseModel):
    default_provider: str
    default_model: str
    planner_provider: str
    planner_model: str
    synthesizer_provider: str
    synthesizer_model: str
    reviewer_provider: str
    reviewer_model: str
    writer_provider: str
    writer_model: str


class RoutingResponse(RoutingUpdate):
    pass


class SignupModeUpdate(BaseModel):
    mode: str = Field(pattern="^(invite|open)$")


class SignupModeResponse(BaseModel):
    mode: str


class UsagePoint(BaseModel):
    date: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class UsageSummaryResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    series: List[UsagePoint]
    by_model: List[dict]


class UsageByUserRow(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
