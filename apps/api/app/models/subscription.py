"""Subscription model — billing tier and lifecycle for a user.

Tiers: free | pro | agency. This table is the authoritative record for
billing state; ``User.plan`` mirrors the active tier for fast reads and
authorization checks.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    # free | pro | agency
    tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    # active | trialing | past_due | canceled
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Billing-provider references (populated once Stripe is wired up).
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="subscription")
