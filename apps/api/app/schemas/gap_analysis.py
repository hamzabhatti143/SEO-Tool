"""Pydantic schemas for the Content Gap Analysis module."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.competitor import UserProjectSummary

Priority = Literal["high", "medium", "low"]
ContentType = Literal["blog", "product_description", "landing_page"]


class GapAnalysisRequest(BaseModel):
    project_id: uuid.UUID
    competitor_urls: list[str] = Field(..., min_length=1, max_length=3)


class ContentBrief(BaseModel):
    """An actionable brief for a single content opportunity."""

    title: str
    target_keyword: str
    content_type: ContentType = "blog"
    outline: list[str]
    word_count_target: int
    priority: Priority
    rationale: str

    @field_validator("priority", "content_type", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v


class GapAnalysisOutput(BaseModel):
    """Structured output produced by the gap-analysis agent."""

    missing_topics: list[str]
    missing_faqs: list[str]
    content_briefs: list[ContentBrief]


class CompetitorSummary(BaseModel):
    url: str
    domain: str
    pages_crawled: int
    sample_titles: list[str] = Field(default_factory=list)


class GapAnalysisResponse(BaseModel):
    user_project: UserProjectSummary
    competitors: list[CompetitorSummary]
    missing_topics: list[str]
    missing_faqs: list[str]
    content_briefs: list[ContentBrief]
