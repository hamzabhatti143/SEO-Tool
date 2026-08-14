"""Pydantic schemas for the Rank Tracking module."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackedKeywordCreate(BaseModel):
    project_id: uuid.UUID
    keyword: str = Field(..., min_length=1, max_length=255)


class RankSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checked_on: date
    position: int | None = None
    url: str | None = None


class TrackedKeywordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    keyword: str
    created_at: datetime
    latest_position: int | None = None
    latest_url: str | None = None
    latest_checked_on: date | None = None


class KeywordHistory(BaseModel):
    id: uuid.UUID
    keyword: str
    snapshots: list[RankSnapshotRead]


class RankHistoryResponse(BaseModel):
    serpapi_configured: bool
    keywords: list[KeywordHistory]


class RefreshResponse(BaseModel):
    serpapi_configured: bool
    checked: int
    keywords: list[TrackedKeywordRead]
