"""Content Gap Analysis routes.

Crawls 2-3 competitors, so it runs in the ARQ worker: POST enqueues a job
and returns a job id; poll GET /jobs/{id} for the result.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import tasks
from app.api.deps import ensure_project_access, get_current_user
from app.core.queue import dispatch, get_arq_optional
from app.db.base import get_db
from app.models.user import User
from app.schemas.gap_analysis import GapAnalysisRequest
from app.schemas.jobs import JobEnqueued

router = APIRouter()


@router.post(
    "/analyze", response_model=JobEnqueued, status_code=status.HTTP_202_ACCEPTED
)
async def analyze_gaps(
    payload: GapAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq=Depends(get_arq_optional),
) -> JobEnqueued:
    """Enqueue content gap analysis. Poll /jobs/{id} for the result."""
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )
    job_id = await dispatch(
        arq,
        "task_analyze_gaps",
        tasks.task_analyze_gaps,
        str(payload.project_id),
        payload.competitor_urls,
    )
    return JobEnqueued(job_id=job_id)
