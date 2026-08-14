"""Content model — an AI-generated SEO blog post."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Content(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    target_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    # blog | product_description | landing_page
    content_type: Mapped[str] = mapped_column(
        String(30), default="blog", nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_description: Mapped[str | None] = mapped_column(String(320), nullable=True)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    # draft | published
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)

    project: Mapped[Project] = relationship(back_populates="content")
