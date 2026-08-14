"""Keyword model — a term surfaced by keyword research."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Keyword(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "keywords"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # The seed keyword this term was generated from.
    seed_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    # Classification produced by the AI: "related" | "long_tail" | "question"
    kind: Mapped[str] = mapped_column(String(20), default="related", nullable=False)
    # informational | commercial | transactional
    search_intent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # AI-estimated difficulty: "low" | "medium" | "high"
    difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    search_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Topic clustering (embeddings + cosine similarity).
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cluster_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Google Trends signal (best-effort; may be null if throttled).
    trend_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # rising | falling | flat
    trend_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)

    project: Mapped[Project] = relationship(back_populates="keywords")
