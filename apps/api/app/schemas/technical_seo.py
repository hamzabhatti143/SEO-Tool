"""Pydantic schemas for the Technical-SEO audit (schema / robots / llms.txt)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SchemaAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    page_url: str
    schema_type: str
    fmt: str
    is_valid: bool
    missing_properties: list[str] = Field(default_factory=list)
    raw_schema: dict[str, Any] | None = None
    detected_at: datetime


class RobotsIssue(BaseModel):
    code: str
    severity: str  # critical | warning | info
    message: str


class UserAgentRules(BaseModel):
    user_agent: str
    disallow: list[str] = Field(default_factory=list)
    allow: list[str] = Field(default_factory=list)


class RobotsParsedRules(BaseModel):
    user_agents: list[UserAgentRules] = Field(default_factory=list)
    sitemaps: list[str] = Field(default_factory=list)


class RobotsAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    exists: bool
    raw_content: str | None = None
    parsed_rules: RobotsParsedRules | None = None
    issues_found: list[RobotsIssue] = Field(default_factory=list)
    checked_at: datetime


class LlmsTxtAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    exists: bool
    raw_content: str | None = None
    follows_spec_format: bool
    checked_at: datetime


class TechnicalSeoResponse(BaseModel):
    """Everything the Audit dashboard's technical-SEO tabs need, in one call."""

    schema_audits: list[SchemaAuditRead] = Field(default_factory=list)
    robots: RobotsAuditRead | None = None
    llms: LlmsTxtAuditRead | None = None


class TechnicalIssueRead(BaseModel):
    """A single detected technical-SEO issue (extended detection engine)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    issue_type: str
    page_url: str
    details: dict[str, Any] | None = None
    fix_confidence: str  # auto | suggest | manual
    status: str  # open | fixed | reverted | ignored
    detected_at: datetime


class TechnicalIssueStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|fixed|reverted|ignored)$")
