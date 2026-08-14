"""AutomationSettings model.

One row per project holding which automations are active plus small bits of
job state (last-seen broken links, competitor content hashes) so scheduled
jobs can detect *changes* (new broken links, competitor content changes).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class AutomationSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "automation_settings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # --- Automation toggles ---
    weekly_audit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    broken_link_monitoring: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    competitor_monitoring: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # --- Email notification toggles ---
    email_notifications: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    notify_rank_drops: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    notify_broken_links: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    weekly_summary: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # --- Configuration ---
    # Defaults to the project homepage when null.
    audit_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    monitor_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    competitor_urls: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # Defaults to the project owner's email when null.
    notification_email: Mapped[str | None] = mapped_column(
        String(320), nullable=True
    )

    # --- Job state (managed by the scheduler, not the user) ---
    last_broken_links: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True
    )
    competitor_hashes: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="automation")
