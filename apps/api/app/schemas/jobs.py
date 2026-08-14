"""Pydantic schemas for enqueued background jobs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class JobEnqueued(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"


class JobStatusResponse(BaseModel):
    job_id: str
    # queued | running | complete | failed | not_found
    status: str
    result: Any | None = None
    error: str | None = None
