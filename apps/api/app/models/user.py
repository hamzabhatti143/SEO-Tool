"""User model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.subscription import Subscription


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Denormalized active tier (mirrors Subscription.tier): standard | premium
    plan: Mapped[str] = mapped_column(
        String(20), default="standard", nullable=False
    )
    # Force a password change on next login (admin-created accounts start True).
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Account lifecycle: active | suspended. Suspended accounts cannot log in
    # (enforced in the auth login route); toggled by the super admin.
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )

    projects: Mapped[list[Project]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    subscription: Mapped[Subscription | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
