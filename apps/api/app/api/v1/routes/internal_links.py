"""Internal Link Optimizer routes.

`POST /crawl` crawls the project's own site and persists the page list
(with content summaries + embeddings). `GET /analysis` returns the internal
link graph, orphan pages, and semantic linking suggestions from the stored
pages. Authenticated and project-scoped.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import tasks
from app.api.deps import ensure_project_access, get_current_user
from app.core.queue import dispatch, get_arq_optional
from app.db.base import get_db
from app.models.user import User
from app.schemas.internal_links import AnalysisResponse, CrawlRequest
from app.schemas.jobs import JobEnqueued
from app.services import internal_link_service

router = APIRouter()


@router.post(
    "/crawl", response_model=JobEnqueued, status_code=status.HTTP_202_ACCEPTED
)
async def crawl_project(
    payload: CrawlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq=Depends(get_arq_optional),
) -> JobEnqueued:
    """Enqueue a site crawl (heavy). Poll /jobs/{id}, then GET /analysis."""
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )
    job_id = await dispatch(
        arq,
        "task_crawl_internal_links",
        tasks.task_crawl_internal_links,
        str(payload.project_id),
    )
    return JobEnqueued(job_id=job_id)


@router.get("/analysis", response_model=AnalysisResponse)
async def analysis(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """Return the link graph, orphans, and suggestions from stored pages."""
    project = await ensure_project_access(project_id, current_user, db)
    return await internal_link_service.analyze(db, project)
