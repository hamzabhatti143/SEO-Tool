"""Pydantic schemas for authentication."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class ChangePasswordRequest(BaseModel):
    # Required for a voluntary change; ignored for a forced first-login change
    # (the user has already authenticated with the temporary password).
    current_password: str | None = None
    new_password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
