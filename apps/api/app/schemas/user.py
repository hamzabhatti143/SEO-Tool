"""Pydantic schemas for users and subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Tier = Literal["free", "pro", "agency"]
SubscriptionStatus = Literal["active", "trialing", "past_due", "canceled"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = None


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tier: str
    status: str
    current_period_end: datetime | None = None
    created_at: datetime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    # Active tier, mirrored from the subscription: free | pro | agency
    plan: str
    created_at: datetime
