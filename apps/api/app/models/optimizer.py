"""OnPageAudit model — a recorded On-Page SEO Optimizer run.

Stores the target keywords as a JSON array (the optimizer supports multiple
keywords per URL; ``keywords[0]`` is the primary) rather than a single string
column, alongside the URL and the combined score.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OnPageAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "on_page_audits"

    # Optional: the optimizer can be run as a standalone tool (no project).
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Target keywords as a JSON array; the first entry is the primary keyword.
    keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    primary_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
