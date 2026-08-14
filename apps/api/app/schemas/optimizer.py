"""Pydantic schemas for the On-Page SEO Optimizer module."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "warning", "info"]

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
    target_keyword: str = Field(..., min_length=1, max_length=255)


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
    flesch_reading_ease: float = 0.0
    grade_level: float = 0.0
    # very easy | easy | standard | fairly difficult | difficult
    assessment: str = "standard"


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


class OptimizeResponse(BaseModel):
    url: str
    target_keyword: str
    score: float
    checks: OnPageChecks
    ai_suggestions: AiKeywordSuggestions
    suggestions: list[Suggestion]
