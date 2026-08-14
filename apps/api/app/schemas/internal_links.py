"""Pydantic schemas for the Internal Link Optimizer module."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class CrawlRequest(BaseModel):
    project_id: uuid.UUID


class PageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    title: str | None = None
    content_summary: str | None = None
    word_count: int = 0


class CrawlResponse(BaseModel):
    pages_crawled: int
    pages: list[PageRead]


class GraphNode(BaseModel):
    id: str
    label: str
    url: str
    inbound: int
    outbound: int
    is_orphan: bool


class GraphEdge(BaseModel):
    source: str
    target: str


class LinkSuggestion(BaseModel):
    from_url: str
    from_title: str
    to_url: str
    to_title: str
    anchor_text: str
    similarity: float


class AnalysisResponse(BaseModel):
    page_count: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    suggestions: list[LinkSuggestion]
    orphans: list[PageRead]
