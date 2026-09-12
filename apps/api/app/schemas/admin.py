"""Pydantic schemas for the isolated super-admin system.

These back the ``/api/admin/*`` routes. The super admin authenticates against
env credentials (not the Users table), so there is no user schema here — only
admin login and account-management payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.user import Tier


def _clean_optional_password(value: str | None) -> str | None:
    """Treat blank as "no password"; require 8–128 chars when provided."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(value) > 128:
        raise ValueError("Password must be at most 128 characters.")
    return value


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
    # Optional: set the user's initial password. Left blank, a temporary
    # password is generated and the user is forced to change it on first login.
    password: str | None = None
    # Email the password to the new user when configured.
    send_email: bool = True

    _clean_password = field_validator("password")(_clean_optional_password)


class AccountCreateResponse(BaseModel):
    account: AccountRead
    temporary_password: str
    emailed: bool


class AccountUpdate(BaseModel):
    """Edit account details, change the subscription tier, and/or reset password."""

    full_name: str | None = None
    plan: Tier | None = None
    # Optional: set a new password. Blank/absent leaves the password unchanged.
    password: str | None = None

    _clean_password = field_validator("password")(_clean_optional_password)


class AccountStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|suspended)$")


class AdminStats(BaseModel):
    total: int
    standard: int
    premium: int
    active: int
    suspended: int
