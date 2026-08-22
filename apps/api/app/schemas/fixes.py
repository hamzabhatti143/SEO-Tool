"""Pydantic schemas for the fix orchestration service.

Mirrors the TypeScript types in ``packages/shared`` / ``api.ts``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.connectors import Platform
from app.schemas.core_web_vitals import CoreWebVitalsRead

ChangeStatus = Literal["applied", "reverted"]
# Whether the post-fix re-scan actually ran.
RescanStatus = Literal["completed", "failed", "skipped"]


class FixAllRequest(BaseModel):
    # Which page to fix + re-scan. Defaults to the latest scanned URL for the
    # project, else the project domain.
    url: str | None = Field(default=None, max_length=2048)


class ChangeLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    platform: Platform
    issue_type: str
    external_change_id: str | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    cwv_score_before: float | None = None
    cwv_score_after: float | None = None
    applied_at: datetime
    status: ChangeStatus
    created_at: datetime


class FixResponse(BaseModel):
    """A fix (or revert) result: the change record + the post-action re-scan."""

    change: ChangeLogRead
    new_scan: CoreWebVitalsRead | None = None
    rescan_status: RescanStatus
    detail: str | None = None
