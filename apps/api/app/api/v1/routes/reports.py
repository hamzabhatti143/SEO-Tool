"""Reports routes.

Aggregate Audit + Keyword Research + Content into one branded report per
project, as HTML (always available) or PDF (WeasyPrint; needs native libs).
Agency-plan users get white-label branding from project settings.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user
from app.db.base import get_db
from app.models.user import User
from app.services import report_service

router = APIRouter()


def _filename(project_name: str, ext: str) -> str:
    slug = "".join(
        c if c.isalnum() else "-" for c in project_name.lower()
    ).strip("-")
    return f"seo-report-{slug or 'project'}.{ext}"


@router.get("/{project_id}/html", response_class=HTMLResponse)
async def report_html(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Render the report as HTML (preview / no native deps required)."""
    project = await ensure_project_access(project_id, current_user, db)
    html = await report_service.render_html(db, project, current_user)
    return HTMLResponse(content=html)


@router.get("/{project_id}/pdf")
async def report_pdf(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the report as a downloadable branded PDF."""
    project = await ensure_project_access(project_id, current_user, db)
    html = await report_service.render_html(db, project, current_user)
    try:
        pdf = await report_service.html_to_pdf(html)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_filename(project.name, "pdf")}"'
            )
        },
    )
