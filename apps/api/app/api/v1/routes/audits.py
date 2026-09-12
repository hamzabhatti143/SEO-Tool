"""Website Audit routes.

The crawl is heavy, so it runs in the ARQ worker: POST enqueues a job and
returns a job id; poll GET /jobs/{id} for `{audit_id, score}`, then fetch
the full report via GET /audits/{id}.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import tasks
from app.api.deps import ensure_project_access, get_current_user
from app.core.queue import dispatch, get_arq_optional
from app.db.base import get_db
from app.models.audit import AuditReport
from app.models.technical_seo import TechnicalSEOIssue
from app.models.user import User
from app.schemas.audit import AuditRead, AuditRequest
from app.schemas.jobs import JobEnqueued
from app.schemas.technical_seo import (
    TechnicalIssueRead,
    TechnicalIssueStatusUpdate,
    TechnicalSeoResponse,
)
from app.services import technical_seo_service

router = APIRouter()

# Order issues so actionable, high-confidence findings surface first.
_CONFIDENCE_ORDER = {"auto": 0, "suggest": 1, "manual": 2}


@router.get("/technical-issues", response_model=list[TechnicalIssueRead])
async def list_technical_issues(
    project_id: uuid.UUID,
    issue_type: str | None = None,
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TechnicalSEOIssue]:
    """List the extended technical-SEO issues detected for a project."""
    await ensure_project_access(project_id, current_user, db)
    stmt = select(TechnicalSEOIssue).where(
        TechnicalSEOIssue.project_id == project_id
    )
    if issue_type:
        stmt = stmt.where(TechnicalSEOIssue.issue_type == issue_type)
    if status_filter:
        stmt = stmt.where(TechnicalSEOIssue.status == status_filter)
    rows = list((await db.execute(stmt)).scalars().all())
    rows.sort(
        key=lambda i: (
            _CONFIDENCE_ORDER.get(i.fix_confidence, 3),
            i.issue_type,
        )
    )
    return rows


@router.patch(
    "/technical-issues/{issue_id}/status", response_model=TechnicalIssueRead
)
async def update_technical_issue_status(
    issue_id: uuid.UUID,
    payload: TechnicalIssueStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalSEOIssue:
    """Update an issue's lifecycle status (open/fixed/reverted/ignored)."""
    issue = await db.get(TechnicalSEOIssue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    await ensure_project_access(issue.project_id, current_user, db, min_role="editor")
    issue.status = payload.status
    await db.commit()
    await db.refresh(issue)
    return issue


@router.get("/technical-seo", response_model=TechnicalSeoResponse)
async def get_technical_seo(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalSeoResponse:
    """Structured-data, robots.txt, and llms.txt audit results for a project.

    Populated automatically by the Website Audit scan.
    """
    await ensure_project_access(project_id, current_user, db)
    return await technical_seo_service.get_technical_seo(db, project_id)


@router.post("", response_model=JobEnqueued, status_code=status.HTTP_202_ACCEPTED)
async def create_audit(
    payload: AuditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq=Depends(get_arq_optional),
) -> JobEnqueued:
    """Enqueue an SEO audit. Poll /jobs/{id}; the result carries audit_id."""
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )
    job_id = await dispatch(
        arq,
        "task_run_audit",
        tasks.task_run_audit,
        str(payload.project_id),
        payload.url,
    )
    return JobEnqueued(job_id=job_id)


@router.get("", response_model=list[AuditRead])
async def list_audits(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditReport]:
    """List audit reports for an accessible project, newest first."""
    await ensure_project_access(project_id, current_user, db)
    result = await db.execute(
        select(AuditReport)
        .where(AuditReport.project_id == project_id)
        .order_by(AuditReport.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{audit_id}", response_model=AuditRead)
async def get_audit(
    audit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditReport:
    """Fetch a single audit report the current user owns."""
    audit = await db.get(AuditReport, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit report not found")
    await ensure_project_access(audit.project_id, current_user, db)
    return audit
