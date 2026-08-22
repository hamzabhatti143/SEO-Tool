"""Connector persistence — upsert a project's encrypted credentials.

Shared by both the WordPress and Shopify flows: encrypts the secret, writes
(or updates) the single ``Credentials`` row for the project, and keeps the
project's ``platform`` field in sync.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.models.credentials import Credentials
from app.models.project import Project


async def upsert_credentials(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    platform: str,
    secret: str,
    site_url: str | None,
    status: str = "connected",
) -> Credentials:
    """Create or replace the project's connection and persist it."""
    existing = (
        await db.execute(
            select(Credentials).where(Credentials.project_id == project_id)
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    encrypted = encrypt(secret)

    if existing is None:
        existing = Credentials(project_id=project_id)
        db.add(existing)

    existing.platform = platform
    existing.encrypted_api_key_or_token = encrypted
    existing.site_url = site_url
    existing.status = status
    existing.connected_at = now if status == "connected" else existing.connected_at

    # Keep the denormalized platform on the project in step.
    project = await db.get(Project, project_id)
    if project is not None:
        project.platform = platform

    await db.commit()
    await db.refresh(existing)
    return existing


async def get_credentials(
    db: AsyncSession, project_id: uuid.UUID
) -> Credentials | None:
    """Return the project's connection row, if any."""
    return (
        await db.execute(
            select(Credentials).where(Credentials.project_id == project_id)
        )
    ).scalar_one_or_none()
