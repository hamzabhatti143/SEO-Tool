"""Pydantic schemas for Agency Mode (team, invites, client share links)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["admin", "editor", "viewer"]


class MemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: str
    created_at: datetime


class MemberRoleUpdate(BaseModel):
    role: Role


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role = "viewer"


class InviteRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    token: str
    accepted: bool
    created_at: datetime


class InviteAccept(BaseModel):
    token: str


class InviteAcceptResult(BaseModel):
    project_id: uuid.UUID
    role: str


class ShareLinkCreate(BaseModel):
    label: str | None = Field(default=None, max_length=120)


class ShareLinkRead(BaseModel):
    id: uuid.UUID
    token: str
    label: str | None = None
    revoked: bool
    created_at: datetime
