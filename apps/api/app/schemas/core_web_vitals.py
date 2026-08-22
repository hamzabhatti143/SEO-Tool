"""Pydantic schemas for Core Web Vitals (Website Audit → Performance).

Backed by the Google PageSpeed Insights API v5. A scan requests all four
Lighthouse categories, extracts the lab timing metrics (FCP/LCP/TBT/CLS/Speed
Index), real-user INP from field data (CrUX) when available, per-category
scores, and each category's audits classified into Insights / Diagnostics /
Passed — plus load-timeline screenshots. Mirrors the TS types in
``packages/shared`` / ``api.ts``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Strategy = Literal["mobile", "desktop"]
CategoryKey = Literal["performance", "accessibility", "best_practices", "seo"]


class CoreWebVitalsRequest(BaseModel):
    project_id: uuid.UUID
    url: str = Field(..., min_length=1, max_length=2048)
    strategy: Strategy = "mobile"


class LabMetrics(BaseModel):
    """Lab timing metrics (median across runs). ms except CLS (unitless)."""

    fcp: float | None = None  # First Contentful Paint
    lcp: float | None = None  # Largest Contentful Paint
    tbt: float | None = None  # Total Blocking Time
    cls: float | None = None  # Cumulative Layout Shift
    speed_index: float | None = None


class RunMetrics(LabMetrics):
    """One individual run's metrics (kept for transparency)."""

    performance_score: float | None = None


class AuditItem(BaseModel):
    """A single Lighthouse audit surfaced as an insight or diagnostic."""

    id: str
    title: str
    description: str = ""
    # 0–1 Lighthouse score (None for informational audits).
    score: float | None = None
    # Human "Est savings" / value text Lighthouse provides, e.g. "1.2 s".
    display_value: str | None = None
    # Machine-readable savings for sorting, when present.
    savings_ms: float | None = None
    savings_bytes: int | None = None


class CategoryAudits(BaseModel):
    """A category's score plus its audits grouped for the UI."""

    score: float | None = None  # 0–100
    # Opportunities with estimated savings (performance only, usually).
    insights: list[AuditItem] = Field(default_factory=list)
    # Failing/informational non-opportunity checks.
    diagnostics: list[AuditItem] = Field(default_factory=list)
    passed_count: int = 0
    passed_titles: list[str] = Field(default_factory=list)


class Screenshots(BaseModel):
    """Load-progression thumbnails (base64 data URIs) + final screenshot."""

    timeline: list[str] = Field(default_factory=list)
    final: str | None = None


class ScanMetadata(BaseModel):
    lighthouse_version: str | None = None
    form_factor: str | None = None  # mobile | desktop
    throttling_method: str | None = None  # simulate | devtools | provided
    fetch_time: str | None = None  # ISO timestamp from Lighthouse
    final_url: str | None = None


class CoreWebVitalsReport(BaseModel):
    """The full parsed scan (also the shape the service returns / we store)."""

    strategy: Strategy = "mobile"
    metrics: LabMetrics = Field(default_factory=LabMetrics)  # median
    # Real-user INP (ms) from CrUX field data, or None when unavailable —
    # never fabricated (lab runs have no INP).
    field_inp: float | None = None
    categories: dict[CategoryKey, CategoryAudits] = Field(default_factory=dict)
    screenshots: Screenshots = Field(default_factory=Screenshots)
    metadata: ScanMetadata = Field(default_factory=ScanMetadata)
    runs: list[RunMetrics] = Field(default_factory=list)
    lcp_element: str | None = None


class CoreWebVitalsRead(BaseModel):
    """A stored scan as returned by the API (columns + the rich report)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    url: str
    strategy: Strategy = "mobile"

    # Median lab metrics (columns, for history/trends).
    fcp: float | None = None
    lcp: float | None = None
    tbt: float | None = None
    cls: float | None = None
    speed_index: float | None = None
    field_inp: float | None = None

    # Category scores 0–100 (columns).
    performance_score: float | None = None
    accessibility_score: float | None = None
    best_practices_score: float | None = None
    seo_score: float | None = None

    # Full detail: insights/diagnostics/passed, screenshots, metadata, runs.
    # Nullable so scans stored before this shape (report_json = NULL) still
    # list without a serialization error.
    report: CoreWebVitalsReport | None = Field(
        default=None, validation_alias="report_json"
    )

    scanned_at: datetime
    created_at: datetime
