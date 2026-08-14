"""Automation routes — per-project automation settings + manual runs."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user
from app.db.base import get_db
from app.models.automation import AutomationSettings
from app.models.user import User
from app.schemas.automation import (
    AutomationSettingsRead,
    AutomationSettingsUpdate,
)
from app.services import automation_service

router = APIRouter()


async def _get_or_create(
    db: AsyncSession, project_id: uuid.UUID
) -> AutomationSettings:
    settings_row = (
        await db.execute(
            select(AutomationSettings).where(
                AutomationSettings.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if settings_row is None:
        settings_row = AutomationSettings(project_id=project_id)
        db.add(settings_row)
        await db.commit()
        await db.refresh(settings_row)
    return settings_row


@router.get("/settings", response_model=AutomationSettingsRead)
async def get_settings(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomationSettings:
    """Get (creating defaults if needed) automation settings for a project."""
    await ensure_project_access(project_id, current_user, db)
    return await _get_or_create(db, project_id)


@router.put("/settings", response_model=AutomationSettingsRead)
async def update_settings(
    project_id: uuid.UUID,
    payload: AutomationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomationSettings:
    """Update which automations are active (and their config) for a project."""
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    row = await _get_or_create(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/run")
async def run_now(
    project_id: uuid.UUID,
    kind: Literal["daily", "weekly"],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run this project's daily or weekly automations immediately."""
    await ensure_project_access(project_id, current_user, db, min_role="editor")
    try:
        if kind == "daily":
            await automation_service.run_daily(db, project_id=project_id)
        else:
            await automation_service.run_weekly(db, project_id=project_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Automation run failed: {exc}",
        ) from exc
    return {"status": "completed", "kind": kind}
