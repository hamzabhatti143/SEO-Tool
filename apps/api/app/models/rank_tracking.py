"""Rank Tracking models.

`TrackedKeyword` — a keyword the user wants to track SERP position for.
`RankSnapshot` — one daily (date, position, url) measurement for a tracked
keyword. Positions come from SerpApi (see app.services.serpapi_service).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class TrackedKeyword(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tracked_keywords"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "keyword", name="uq_tracked_keywords_project_keyword"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)

    project: Mapped[Project] = relationship(back_populates="tracked_keywords")
    snapshots: Mapped[list[RankSnapshot]] = relationship(
        back_populates="tracked_keyword", cascade="all, delete-orphan"
    )


class RankSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rank_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tracked_keyword_id",
            "checked_on",
            name="uq_rank_snapshots_keyword_date",
        ),
    )

    tracked_keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_keywords.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    checked_on: Mapped[date] = mapped_column(Date, nullable=False)
    # 1-based SERP position, or NULL if not found within SERPAPI_NUM results.
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    tracked_keyword: Mapped[TrackedKeyword] = relationship(
        back_populates="snapshots"
    )
