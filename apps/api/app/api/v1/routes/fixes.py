"""Core Web Vitals fix orchestration routes.

Mounted under ``/projects`` so the paths read ``/projects/{id}/cwv/...``.
Both fix-all and revert route by the project's ``platform`` field to the
matching (stubbed) handler, then trigger a re-scan and log the change.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user
from app.db.base import get_db
from app.models.change_log import ChangeLog
from app.models.user import User
from app.schemas.core_web_vitals import CoreWebVitalsRead
from app.schemas.fixes import ChangeLogRead, FixAllRequest, FixResponse
from app.services import fix_service
from app.services.fix_service import FixError, OrchestrationResult

router = APIRouter()


def _to_response(result: OrchestrationResult) -> FixResponse:
    return FixResponse(
        change=ChangeLogRead.model_validate(result.change),
        new_scan=(
            CoreWebVitalsRead.model_validate(result.new_scan)
            if result.new_scan is not None
            else None
        ),
        rescan_status=result.rescan_status,  # type: ignore[arg-type]
        detail=result.detail,
    )


@router.post("/{project_id}/cwv/fix-all", response_model=FixResponse)
async def fix_all(
    project_id: uuid.UUID,
    payload: FixAllRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FixResponse:
    """Apply all CWV fixes for the project (routed by platform), then re-scan."""
    project = await ensure_project_access(
        project_id, current_user, db, min_role="editor"
    )
    url = await fix_service.resolve_target_url(
        db, project, payload.url if payload else None
    )
    try:
        result = await fix_service.apply_fix_all(db, project, url)
    except FixError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return _to_response(result)


@router.post("/{project_id}/cwv/revert/{change_id}", response_model=FixResponse)
async def revert(
    project_id: uuid.UUID,
    change_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FixResponse:
    """Revert a logged change (routed by platform), then re-scan."""
    project = await ensure_project_access(
        project_id, current_user, db, min_role="editor"
    )
    change = await db.get(ChangeLog, change_id)
    if change is None or change.project_id != project_id:
        raise HTTPException(status_code=404, detail="Change not found")

    try:
        result = await fix_service.revert_fix(db, project, change)
    except FixError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return _to_response(result)


@router.get("/{project_id}/cwv/changes", response_model=list[ChangeLogRead])
async def list_changes(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChangeLog]:
    """List the project's change log, newest first."""
    await ensure_project_access(project_id, current_user, db)
    result = await db.execute(
        select(ChangeLog)
        .where(ChangeLog.project_id == project_id)
        .order_by(ChangeLog.applied_at.desc())
    )
    return list(result.scalars().all())
