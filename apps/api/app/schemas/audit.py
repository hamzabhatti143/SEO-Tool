"""Pydantic schemas for the Website Audit module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuditStatus = Literal["queued", "running", "completed", "failed"]
IssueSeverity = Literal["info", "warning", "critical"]


class AuditRequest(BaseModel):
    project_id: uuid.UUID
    url: str = Field(..., min_length=1, max_length=2048)


class MetaTagReport(BaseModel):
    title: str | None = None
    title_length: int = 0
    meta_description: str | None = None
    meta_description_length: int = 0
    has_canonical: bool = False
    has_viewport: bool = False
    has_open_graph: bool = False
    robots: str | None = None


class HeadingReport(BaseModel):
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    h4_count: int = 0
    h5_count: int = 0
    h6_count: int = 0
    h1_texts: list[str] = Field(default_factory=list)


class ImageReport(BaseModel):
    total: int = 0
    missing_alt: int = 0
    # A few example sources that are missing alt text (for the UI).
    missing_alt_samples: list[str] = Field(default_factory=list)


class BrokenLink(BaseModel):
    url: str
    status_code: int | None = None
    reason: str


class LinkReport(BaseModel):
    internal_count: int = 0
    external_count: int = 0
    checked: int = 0
    # Only internal links are checked for breakage.
    broken: list[BrokenLink] = Field(default_factory=list)


class PageSpeedReport(BaseModel):
    response_time_ms: float
    page_size_kb: float
    request_count_estimate: int
    status_code: int


class AuditIssue(BaseModel):
    code: str
    severity: IssueSeverity
    message: str
    recommendation: str


class AuditResults(BaseModel):
    meta: MetaTagReport
    headings: HeadingReport
    images: ImageReport
    links: LinkReport
    page_speed: PageSpeedReport
    issues: list[AuditIssue] = Field(default_factory=list)


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    url: str
    status: AuditStatus
    score: float | None = None
    results: AuditResults | None = None
    created_at: datetime
    completed_at: datetime | None = None
