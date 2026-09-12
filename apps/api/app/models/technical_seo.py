"""Technical-SEO audit models: structured data, robots.txt, and llms.txt.

Populated automatically by the Website Audit scan (see
``app.services.technical_seo_service`` + ``tasks.task_run_audit``). Each scan
replaces the project's previous rows so the tables hold the current state.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class SchemaAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One detected structured-data (schema.org) block on a page."""

    __tablename__ = "schema_audits"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    page_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    schema_type: Mapped[str] = mapped_column(String(128), nullable=False)
    # json-ld | microdata | rdfa
    fmt: Mapped[str] = mapped_column(String(16), nullable=False, default="json-ld")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    missing_properties: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True
    )
    raw_schema: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="schema_audits")


class RobotsAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """robots.txt fetch + parse for a project's site."""

    __tablename__ = "robots_audits"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    exists: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"user_agents": [{"user_agent", "disallow": [], "allow": []}], "sitemaps": []}
    parsed_rules: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    issues_found: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="robots_audits")


class TechnicalSEOIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One technical-SEO issue detected during a project scan.

    ``details`` is a per-type JSON payload (broken-link target + suggested
    replacement, redirect chain array, duplicate-group urls, etc.). Each scan
    replaces the project's previous issues so the table reflects current state.
    """

    __tablename__ = "technical_seo_issues"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # broken_internal_link | broken_external_link | redirect_chain |
    # missing_canonical | incorrect_canonical | missing_sitemap |
    # sitemap_errors | duplicate_content | orphan_pages | mixed_content |
    # missing_alt_text
    issue_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    page_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # auto | suggest | manual
    fix_confidence: Mapped[str] = mapped_column(
        String(16), default="manual", nullable=False
    )
    # open | fixed | reverted | ignored
    status: Mapped[str] = mapped_column(
        String(16), default="open", server_default="open", nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(
        back_populates="technical_seo_issues"
    )


class LlmsTxtAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """llms.txt fetch + spec-format check for a project's site."""

    __tablename__ = "llms_txt_audits"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    exists: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    follows_spec_format: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="llms_txt_audits")
