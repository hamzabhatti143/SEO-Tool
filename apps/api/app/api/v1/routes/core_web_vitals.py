"""Core Web Vitals routes (Website Audit → Performance).

`POST /audit/core-web-vitals` runs a Lighthouse scan synchronously, persists a
`CoreWebVitals` row, and returns the parsed metrics + structured issues. The
scan takes ~15–45s, so the client shows a spinner; there is no queue hop.
List/detail routes read stored scans, newest first.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user
from app.db.base import get_db
from app.models.core_web_vitals import CoreWebVitals
from app.models.user import User
from app.schemas.core_web_vitals import (
    CoreWebVitalsRead,
    CoreWebVitalsRequest,
)
from app.services import core_web_vitals_service
from app.services.core_web_vitals_service import CoreWebVitalsError

router = APIRouter()


@router.post("/core-web-vitals", response_model=CoreWebVitalsRead)
async def run_core_web_vitals(
    payload: CoreWebVitalsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoreWebVitals:
    """Run a Core Web Vitals scan, store it, and return the results."""
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )

    try:
        return await core_web_vitals_service.scan_and_store(
            db, payload.project_id, payload.url, payload.strategy
        )
    except CoreWebVitalsError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Core Web Vitals scan failed: {exc}",
        ) from exc


@router.get("/core-web-vitals", response_model=list[CoreWebVitalsRead])
async def list_core_web_vitals(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CoreWebVitals]:
    """List Core Web Vitals scans for an accessible project, newest first."""
    await ensure_project_access(project_id, current_user, db)
    result = await db.execute(
        select(CoreWebVitals)
        .where(CoreWebVitals.project_id == project_id)
        .order_by(CoreWebVitals.scanned_at.desc())
    )
    return list(result.scalars().all())


@router.get("/core-web-vitals/{scan_id}", response_model=CoreWebVitalsRead)
async def get_core_web_vitals(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoreWebVitals:
    """Fetch a single stored Core Web Vitals scan the user can access."""
    scan = await db.get(CoreWebVitals, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    await ensure_project_access(scan.project_id, current_user, db)
    return scan
