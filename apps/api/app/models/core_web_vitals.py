"""CoreWebVitals model — a PageSpeed Insights scan of a single URL.

Stores the median lab timing metrics (FCP/LCP/TBT/CLS/Speed Index), real-user
field INP when available, the four Lighthouse category scores, and the full
parsed report (insights/diagnostics/passed audits, screenshots, metadata, and
each individual run) in ``report_json``. Powers the Website Audit performance
view.
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


class CoreWebVitals(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "core_web_vitals"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # mobile | desktop
    strategy: Mapped[str] = mapped_column(
        String(10), default="mobile", server_default="mobile", nullable=False
    )

    # Median lab timing metrics. All milliseconds except CLS (unitless).
    fcp: Mapped[float | None] = mapped_column(Float, nullable=True)
    lcp: Mapped[float | None] = mapped_column(Float, nullable=True)
    tbt: Mapped[float | None] = mapped_column(Float, nullable=True)
    cls: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Real-user INP (ms) from CrUX field data; NULL when no field data exists.
    field_inp: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lighthouse category scores, 0–100.
    performance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    accessibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_practices_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    seo_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full parsed report (see schemas.CoreWebVitalsReport).
    report_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="core_web_vitals")
