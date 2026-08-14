"""AuditReport model — results of a website SEO audit."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class AuditReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_reports"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Full structured audit output: meta tags, headings, images, links,
    # page-load metrics, and the list of categorized issues.
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="audit_reports")
