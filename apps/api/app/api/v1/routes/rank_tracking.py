"""Rank Tracking routes.

Manage tracked keywords, view rank history for charting, and trigger an
on-demand refresh. The daily cron lives in app.scheduler; these endpoints
let users add/remove keywords and pull results. All are project-scoped.

NOTE: live SERP lookups require a SerpApi API key (free tier ~100
searches/month). Without one, keywords can still be added but positions
stay empty until a key is configured.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user
from app.db.base import get_db
from app.models.rank_tracking import TrackedKeyword
from app.models.user import User
from app.schemas.rank_tracking import (
    RankHistoryResponse,
    RefreshResponse,
    TrackedKeywordCreate,
    TrackedKeywordRead,
)
from app.services import rank_tracking_service, serpapi_service

router = APIRouter()


@router.post(
    "/keywords",
    response_model=TrackedKeywordRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_keyword(
    payload: TrackedKeywordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrackedKeywordRead:
    """Add a keyword to track for a project."""
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )

    existing = (
        await db.execute(
            select(TrackedKeyword).where(
                TrackedKeyword.project_id == payload.project_id,
                TrackedKeyword.keyword == payload.keyword,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Keyword already tracked for this project",
        )

    tk = TrackedKeyword(
        project_id=payload.project_id, keyword=payload.keyword
    )
    db.add(tk)
    await db.commit()
    await db.refresh(tk)
    return TrackedKeywordRead(
        id=tk.id,
        project_id=tk.project_id,
        keyword=tk.keyword,
        created_at=tk.created_at,
    )


@router.get("/keywords", response_model=list[TrackedKeywordRead])
async def list_keywords(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackedKeywordRead]:
    """List tracked keywords (with their latest position)."""
    project = await ensure_project_access(project_id, current_user, db)
    return await rank_tracking_service.list_tracked(db, project)


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop tracking a keyword (removes its history)."""
    tk = await db.get(TrackedKeyword, keyword_id)
    if tk is None:
        raise HTTPException(status_code=404, detail="Tracked keyword not found")
    await ensure_project_access(
        tk.project_id, current_user, db, min_role="editor"
    )
    await db.delete(tk)
    await db.commit()


@router.get("/history", response_model=RankHistoryResponse)
async def history(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RankHistoryResponse:
    """Return rank history per keyword for charting."""
    project = await ensure_project_access(project_id, current_user, db)
    return await rank_tracking_service.get_history(db, project)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """Run rank checks now for this project (consumes SerpApi quota)."""
    project = await ensure_project_access(
        project_id, current_user, db, min_role="editor"
    )
    if not serpapi_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "SerpApi is not configured. Set SERPAPI_API_KEY "
                "(free tier ~100 searches/month) to fetch live rankings."
            ),
        )
    checked = await rank_tracking_service.track_project(db, project)
    keywords = await rank_tracking_service.list_tracked(db, project)
    return RefreshResponse(
        serpapi_configured=True, checked=checked, keywords=keywords
    )
