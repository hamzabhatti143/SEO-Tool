"""Pydantic schemas for the AI Content Studio module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ContentStatus = Literal["draft", "published"]
ContentType = Literal["blog", "product_description", "landing_page"]
ContentTone = Literal["professional", "casual", "authoritative", "friendly"]


class ContentGenerateRequest(BaseModel):
    project_id: uuid.UUID
    topic: str = Field(..., min_length=1, max_length=255)
    target_keyword: str = Field(..., min_length=1, max_length=255)
    content_type: ContentType = "blog"
    tone: ContentTone = "professional"
    # Optional length hint for the drafting stage (not shown in the form).
    word_count: int = Field(default=900, ge=300, le=3000)


class KeywordDensityReport(BaseModel):
    """Deterministic keyword-density check produced in the SEO pass."""

    keyword: str
    occurrences: int
    word_count: int
    density_pct: float
    # low | optimal | high
    assessment: str
    recommendation: str


class ContentGenerationResult(BaseModel):
    """Final result of the content chain (non-streaming path)."""

    title: str
    meta_title: str
    meta_description: str
    body_markdown: str
    outline: list[str]
    density: KeywordDensityReport


class ContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    topic: str
    target_keyword: str
    content_type: str
    title: str
    meta_description: str | None = None
    body_markdown: str
    status: str
    created_at: datetime
