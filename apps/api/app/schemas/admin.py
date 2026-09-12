"""Pydantic schemas for the isolated super-admin system.

These back the ``/api/admin/*`` routes. The super admin authenticates against
env credentials (not the Users table), so there is no user schema here — only
admin login and account-management payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user import Tier


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AccountRead(BaseModel):
    """A user account as seen by the admin dashboard (with project count)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    plan: str
    status: str
    must_change_password: bool = False
    project_count: int = 0
    created_at: datetime


class AccountCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    plan: Tier = "standard"
    # Email the temporary password to the new user when configured.
    send_email: bool = True


class AccountCreateResponse(BaseModel):
    account: AccountRead
    temporary_password: str
    emailed: bool


class AccountUpdate(BaseModel):
    """Edit account details and/or change the subscription tier."""

    full_name: str | None = None
    plan: Tier | None = None


class AccountStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|suspended)$")


class AdminStats(BaseModel):
    total: int
    standard: int
    premium: int
    active: int
    suspended: int
