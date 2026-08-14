"""ProjectPage model — a crawled page of a user's own project.

Stores the page list, a content summary, an embedding, and the internal
links each page points to. Powers the Internal Link Optimizer.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ProjectPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_pages"
    __table_args__ = (
        UniqueConstraint("project_id", "url", name="uq_project_pages_project_url"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Embedding vector (text-embedding-3-small) stored as a JSON float array.
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    # Normalized internal URLs this page links out to.
    outbound_internal_links: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="pages")
