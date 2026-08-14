"""Pydantic schemas for the Competitor Intelligence module.

Data provenance is explicit. Metrics fall into two classes:

* **Measured** — derived deterministically from an actual crawl (page counts,
  internal links, sitemap URLs, titles/headings, topic overlap). These are
  reproducible for an unchanged site.
* **AI-estimated** — inferred by the LLM from on-page signals only
  (traffic band, pseudo-authority). These are NOT from SEMrush, Ahrefs, or
  any paid API and MUST be labeled "AI Estimated" in the UI.

When a real SEO data provider is connected (see
``app.services.seo_data_provider``) the relevant figures carry
``source="provider"`` instead of ``"ai_estimate"``.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Emphasis = Literal["low", "medium", "high"]
MetricSource = Literal["ai_estimate", "provider"]

_DISCLAIMER = (
    "Page counts, internal links, sitemap URLs and topic overlap are measured "
    "from an actual crawl. Traffic and authority figures are AI-estimated from "
    "publicly crawlable on-page signals — not sourced from SEMrush, Ahrefs, or "
    "any paid API. Connect an SEO data provider for first-party figures."
)


class CompetitorRequest(BaseModel):
    project_id: uuid.UUID
    competitor_url: str = Field(..., min_length=1, max_length=2048)


# --- Crawl status -------------------------------------------------------
class CrawlStatus(BaseModel):
    """Whether a site was crawled successfully, and why not if it wasn't.

    ``reason`` is a stable machine code (e.g. "ok", "dns_error",
    "connection_error", "timeout", "robots_blocked", "http_error",
    "non_html", "empty"); ``detail`` is a human-readable explanation.
    """

    ok: bool = True
    reason: str = "ok"
    detail: str = ""


# --- Crawl (deterministic / measured) ----------------------------------
class CrawledPage(BaseModel):
    url: str
    status_code: int | None = None
    title: str | None = None
    h1: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    heading_count: int = 0
    word_count: int = 0
    internal_link_count: int = 0
    external_link_count: int = 0
    indexable: bool = True


class HubPage(BaseModel):
    url: str
    inbound_links: int


class SiteStructure(BaseModel):
    pages_crawled: int = 0
    pages_discovered: int = 0
    # From sitemap(s) if available (best-effort), else null.
    sitemap_url_count: int | None = None
    total_internal_links: int = 0
    avg_internal_links_per_page: float = 0.0
    # Average visible word count across crawled pages, and how many crawled
    # pages are indexable (no meta-robots noindex).
    avg_word_count: float = 0.0
    indexable_pages: int = 0
    # Duplicate URLs collapsed to their rel=canonical target during the crawl.
    duplicate_pages_collapsed: int = 0
    # URLs skipped because robots.txt disallowed them for our user-agent.
    disallowed_by_robots: int = 0
    top_hub_pages: list[HubPage] = Field(default_factory=list)


class CompetitorProfile(BaseModel):
    url: str
    domain: str
    crawl_status: CrawlStatus = Field(default_factory=CrawlStatus)
    sample_titles: list[str] = Field(default_factory=list)
    top_headings: list[str] = Field(default_factory=list)
    structure: SiteStructure = Field(default_factory=SiteStructure)
    pages: list[CrawledPage] = Field(default_factory=list)


# --- Deterministic comparison (measured) --------------------------------
class SiteTopics(BaseModel):
    """Frequency-ranked topics/keywords extracted from a site's crawl."""

    domain: str
    topics: list[str] = Field(default_factory=list)


class Comparison(BaseModel):
    """Deterministic overlap/gap computed from both crawls (not the LLM)."""

    user_topics: list[str] = Field(default_factory=list)
    competitor_topics: list[str] = Field(default_factory=list)
    shared_topics: list[str] = Field(default_factory=list)
    # Competitor topics the user's crawled site does not cover.
    keyword_gaps: list[str] = Field(default_factory=list)
    # Topics the user covers that the competitor does not.
    user_advantages: list[str] = Field(default_factory=list)


# --- AI analysis (narrative + explicitly-estimated figures) -------------
class TopicFocus(BaseModel):
    topic: str
    emphasis: Emphasis
    note: str = ""

    @field_validator("emphasis", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v


class ContentGap(BaseModel):
    topic: str
    rationale: str


class CompetitorAnalysis(BaseModel):
    content_strategy: str
    topic_focus_areas: list[TopicFocus] = Field(default_factory=list)
    # AI-estimated, e.g. "1K–10K / mo". NOT real analytics.
    estimated_traffic_band: str = ""
    traffic_source: MetricSource = "ai_estimate"
    # AI-estimated 0–100 pseudo-authority. NOT Moz/Ahrefs DA/DR.
    estimated_authority: int = 0
    authority_source: MetricSource = "ai_estimate"
    # Same estimates for the USER's own site, so the comparison is symmetric.
    user_estimated_traffic_band: str = ""
    user_traffic_source: MetricSource = "ai_estimate"
    user_estimated_authority: int = 0
    user_authority_source: MetricSource = "ai_estimate"
    # These three are filled deterministically from the crawl comparison,
    # then explained by the LLM — they are measured, not invented.
    keyword_gaps: list[str] = Field(default_factory=list)
    content_gaps: list[ContentGap] = Field(default_factory=list)
    shared_topics: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# --- AI narrative-only output (what the LLM actually returns) ------------
class CompetitorNarrative(BaseModel):
    """Structured output requested from the agent — narrative fields only.

    Quantitative gaps/overlap are computed deterministically and merged in by
    the service, so the LLM never invents competitor pages or keywords.
    """

    content_strategy: str
    topic_focus_areas: list[TopicFocus] = Field(default_factory=list)
    estimated_traffic_band: str = ""
    estimated_authority: int = 0
    user_estimated_traffic_band: str = ""
    user_estimated_authority: int = 0
    content_gap_rationales: list[ContentGap] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# --- User side + full report -------------------------------------------
class UserProjectSummary(BaseModel):
    project_name: str
    domain: str
    keyword_count: int
    content_count: int
    top_keywords: list[str] = Field(default_factory=list)
    top_topics: list[str] = Field(default_factory=list)


class CompetitorReport(BaseModel):
    competitor: CompetitorProfile
    # The user's own site, crawled with the SAME methodology for a fair,
    # symmetric comparison.
    user_site: CompetitorProfile
    user_project: UserProjectSummary
    comparison: Comparison = Field(default_factory=Comparison)
    analysis: CompetitorAnalysis
    ai_estimated: bool = True
    disclaimer: str = _DISCLAIMER
