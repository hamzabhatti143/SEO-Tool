"""Pydantic schemas for the On-Page SEO Optimizer module."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["critical", "warning", "info"]
# The first keyword in the list is the primary (weighted more heavily); the
# rest are secondary.
KeywordRole = Literal["primary", "secondary"]

# Categories double as the section ids in the UI.
Category = Literal[
    "meta_title",
    "meta_description",
    "headings",
    "keyword_placement",
    "keyword_density",
    "links",
    "images",
    "readability",
    "ai",
]


class OptimizeRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    # One or more target keywords; the first is treated as primary. Replaces
    # the old single ``target_keyword`` string.
    keywords: list[str] = Field(..., min_length=1, max_length=10)
    # Optional: when set, the run is recorded against this project.
    project_id: uuid.UUID | None = None

    @field_validator("keywords")
    @classmethod
    def _normalize_keywords(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            kw = raw.strip()
            if not kw:
                continue
            if len(kw) > 255:
                kw = kw[:255]
            key = kw.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(kw)
        if not cleaned:
            raise ValueError("Provide at least one non-empty keyword.")
        return cleaned


class MetaTitleCheck(BaseModel):
    text: str | None = None
    length: int = 0
    has_keyword: bool = False
    keyword_at_start: bool = False


class MetaDescriptionCheck(BaseModel):
    text: str | None = None
    length: int = 0
    has_keyword: bool = False


class HeadingCheck(BaseModel):
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    h4_count: int = 0
    h5_count: int = 0
    h6_count: int = 0
    h1_has_keyword: bool = False
    subheading_has_keyword: bool = False
    h1_texts: list[str] = Field(default_factory=list)


class KeywordPlacementCheck(BaseModel):
    in_title: bool = False
    in_meta_description: bool = False
    in_h1: bool = False
    in_subheadings: bool = False
    in_first_paragraph: bool = False
    in_url: bool = False
    in_image_alt: bool = False
    placement_score: float = 0.0


class KeywordDensityCheck(BaseModel):
    keyword: str
    occurrences: int = 0
    word_count: int = 0
    density_pct: float = 0.0
    # low | optimal | high
    assessment: str = "low"


class AnchorSample(BaseModel):
    text: str  # the anchor text
    href: str  # the link the anchor points to
    kind: Literal["internal", "external"]
    generic: bool = False
    location: str = "body"  # where on the page the anchor sits


class LinkCheck(BaseModel):
    internal_count: int = 0
    external_count: int = 0
    generic_anchor_count: int = 0
    samples: list[AnchorSample] = Field(default_factory=list)


class ImageCheck(BaseModel):
    total: int = 0
    missing_alt: int = 0
    with_keyword_alt: int = 0


class ReadabilityCheck(BaseModel):
    # None when readability could not be computed (empty/too-short page or a
    # textstat failure) — the UI shows "Data not available" rather than a
    # misleading 0.0.
    flesch_reading_ease: float | None = None
    grade_level: float | None = None
    # very easy | easy | standard | fairly difficult | difficult | unavailable
    assessment: str = "unavailable"


class OnPageChecks(BaseModel):
    meta_title: MetaTitleCheck
    meta_description: MetaDescriptionCheck
    headings: HeadingCheck
    keyword_placement: KeywordPlacementCheck
    keyword_density: KeywordDensityCheck
    links: LinkCheck
    images: ImageCheck
    readability: ReadabilityCheck


class AiKeywordSuggestions(BaseModel):
    """LSI/NLP terms and missing keyword recommendations from the AI."""

    lsi_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    notes: str = ""


class Suggestion(BaseModel):
    category: Category
    severity: Severity
    message: str
    recommendation: str


class KeywordAnalysis(BaseModel):
    """The full set of checks + suggestions for a single target keyword."""

    keyword: str
    role: KeywordRole
    # This keyword's own 0–100 score.
    score: float
    checks: OnPageChecks
    ai_suggestions: AiKeywordSuggestions
    suggestions: list[Suggestion]


class OptimizeResponse(BaseModel):
    url: str
    # All target keywords analyzed; ``keywords[0]`` is the primary.
    keywords: list[str]
    primary_keyword: str
    # Combined score across all keywords (primary weighted more heavily).
    score: float
    per_keyword: list[KeywordAnalysis]
