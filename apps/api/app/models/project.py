"""Project model — a website/property being optimized."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agency import ClientShareLink, ProjectInvite, ProjectMember
    from app.models.audit import AuditReport
    from app.models.automation import AutomationSettings
    from app.models.change_log import ChangeLog
    from app.models.content import Content
    from app.models.core_web_vitals import CoreWebVitals
    from app.models.credentials import Credentials
    from app.models.keyword import Keyword
    from app.models.page import ProjectPage
    from app.models.rank_tracking import TrackedKeyword
    from app.models.user import User


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), nullable=False)

    # Which CMS/commerce platform this project is connected to, if any.
    # One of: wordpress | shopify | custom (default).
    platform: Mapped[str] = mapped_column(
        String(20), default="custom", server_default="custom", nullable=False
    )

    # White-label branding (applied in the dashboard + reports for Agency).
    brand_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    brand_logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    custom_domain: Mapped[str | None] = mapped_column(String(253), nullable=True)

    owner: Mapped[User] = relationship(back_populates="projects")
    audit_reports: Mapped[list[AuditReport]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    core_web_vitals: Mapped[list[CoreWebVitals]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    credentials: Mapped[Credentials | None] = relationship(
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    change_logs: Mapped[list[ChangeLog]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    keywords: Mapped[list[Keyword]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    content: Mapped[list[Content]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    pages: Mapped[list[ProjectPage]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tracked_keywords: Mapped[list[TrackedKeyword]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    automation: Mapped[AutomationSettings | None] = relationship(
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    members: Mapped[list[ProjectMember]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    invites: Mapped[list[ProjectInvite]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    share_links: Mapped[list[ClientShareLink]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
