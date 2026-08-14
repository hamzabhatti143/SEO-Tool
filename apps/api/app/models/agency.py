"""Agency Mode models: team membership, invites, and client share links."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project

# Role hierarchy: viewer < editor < admin (< owner, implicit via ownership).
ROLE_ORDER = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


class ProjectMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "user_id", name="uq_project_members_project_user"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), default="viewer", nullable=False)

    project: Mapped[Project] = relationship(back_populates="members")


class ProjectInvite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_invites"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="viewer", nullable=False)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped[Project] = relationship(back_populates="invites")


class ClientShareLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A read-only shareable link so clients can view reports without login."""

    __tablename__ = "client_share_links"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped[Project] = relationship(back_populates="share_links")
