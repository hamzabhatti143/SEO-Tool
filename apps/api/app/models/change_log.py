"""ChangeLog model — an applied (and revertible) platform fix.

Records each automated fix RankPilot pushes to a connected platform, with
enough context to revert it and to measure its Core Web Vitals impact:
the platform's own change handle (a WordPress change id or a Shopify backup
theme id), before/after snapshots, and the CWV score on either side.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ChangeLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "change_log"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # wordpress | shopify (the platform the fix was applied to)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    # What was fixed, e.g. "core_web_vitals".
    issue_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # The platform's handle for undoing this change: a WordPress change id or
    # a Shopify backup theme id.
    external_change_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    cwv_score_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    cwv_score_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # applied | reverted
    status: Mapped[str] = mapped_column(
        String(20), default="applied", nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="change_logs")
