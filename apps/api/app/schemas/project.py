"""Pydantic schemas for projects."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["wordpress", "shopify", "custom"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    domain: str = Field(..., min_length=1, max_length=253)


class ProjectUpdate(BaseModel):
    """Partial update — including white-label branding settings."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    domain: str | None = Field(default=None, min_length=1, max_length=253)
    brand_name: str | None = Field(default=None, max_length=120)
    brand_logo_url: str | None = Field(default=None, max_length=2048)
    brand_color: str | None = Field(default=None, max_length=9)
    custom_domain: str | None = Field(default=None, max_length=253)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    domain: str
    platform: Platform = "custom"
    brand_name: str | None = None
    brand_logo_url: str | None = None
    brand_color: str | None = None
    custom_domain: str | None = None
    created_at: datetime
