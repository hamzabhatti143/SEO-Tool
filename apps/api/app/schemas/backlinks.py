"""Pydantic schemas for the Backlink Center module."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

_LIMITED_NOTE = (
    "Backlink data comes from a free-tier source and is limited/incomplete. "
    "Add an Ahrefs or Semrush API key later for full data."
)


class BacklinkProfileRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=253)


class AnchorCount(BaseModel):
    anchor: str
    count: int
    percentage: float


class SampleBacklink(BaseModel):
    source_url: str
    source_domain: str
    anchor: str
    nofollow: bool


class BacklinkProfileResponse(BaseModel):
    domain: str
    # openlinkprofiler | ahrefs | semrush | unconfigured | error
    data_source: str
    limited: bool
    referring_domains: int
    total_backlinks: int
    follow_count: int
    nofollow_count: int
    nofollow_ratio: float
    anchor_distribution: list[AnchorCount]
    sample_backlinks: list[SampleBacklink]
    note: str = _LIMITED_NOTE


class BrokenLinkRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class BrokenOutboundLink(BaseModel):
    url: str
    anchor: str
    status_code: int | None = None
    reason: str
    kind: Literal["internal", "external"]


class BrokenLinkResponse(BaseModel):
    url: str
    links_checked: int
    broken_count: int
    broken_links: list[BrokenOutboundLink]
