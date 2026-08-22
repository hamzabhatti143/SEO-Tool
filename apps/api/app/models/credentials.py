"""Credentials model — an encrypted platform connection for a project.

Holds the secret needed to talk to a project's connected platform: a
WordPress plugin API key or a Shopify Admin API access token. The secret is
stored **encrypted at rest** (see app.core.crypto) and never returned by the
API. One connection per project (``project_id`` is unique).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Credentials(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credentials"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    # wordpress | shopify | custom
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    # Fernet-encrypted WordPress API key or Shopify access token.
    encrypted_api_key_or_token: Mapped[str] = mapped_column(Text, nullable=False)
    # WordPress site URL or Shopify shop domain (e.g. shop.myshopify.com).
    site_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # connected | error | disconnected
    status: Mapped[str] = mapped_column(
        String(20), default="connected", nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="credentials")
