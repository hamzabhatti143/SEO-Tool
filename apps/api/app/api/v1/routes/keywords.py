"""Keyword Research routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import tasks
from app.api.deps import ensure_project_access, get_current_user
from app.core.queue import dispatch, get_arq_optional
from app.db.base import get_db
from app.models.keyword import Keyword
from app.models.user import User
from app.schemas.jobs import JobEnqueued
from app.schemas.keyword import KeywordRead, KeywordResearchRequest

router = APIRouter()


@router.post(
    "/research",
    response_model=JobEnqueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def research_keywords(
    payload: KeywordResearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq=Depends(get_arq_optional),
) -> JobEnqueued:
    """Enqueue keyword research (slow: AI + clustering + trends). Poll
    /jobs/{id} for the resulting keyword list."""
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )
    job_id = await dispatch(
        arq,
        "task_research_keywords",
        tasks.task_research_keywords,
        str(payload.project_id),
        payload.seed_keyword,
    )
    return JobEnqueued(job_id=job_id)


@router.get("", response_model=list[KeywordRead])
async def list_keywords(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Keyword]:
    """List keywords for a project the current user owns, newest first."""
    await ensure_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Keyword)
        .where(Keyword.project_id == project_id)
        .order_by(Keyword.created_at.desc())
    )
    return list(result.scalars().all())
