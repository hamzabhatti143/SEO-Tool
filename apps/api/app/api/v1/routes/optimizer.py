"""On-Page SEO Optimizer routes.

Takes a URL + one or more target keywords and returns a per-keyword scored,
categorized on-page report plus a combined score. Requires authentication.
Each run is recorded in ``on_page_audits`` (keywords stored as a JSON array);
persistence is best-effort and never blocks the response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.optimizer import OnPageAudit
from app.models.user import User
from app.schemas.optimizer import OptimizeRequest, OptimizeResponse
from app.services import optimizer_service

router = APIRouter()


@router.post("/analyze", response_model=OptimizeResponse)
async def analyze_on_page(
    payload: OptimizeRequest,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OptimizeResponse:
    """Analyze a page against one or more keywords; return a scored report."""
    try:
        result = await optimizer_service.analyze(payload)
    except Exception as exc:  # noqa: BLE001 - surface crawl/analysis failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"On-page analysis failed: {exc}",
        ) from exc

    # Record the run (keywords as a JSON array). Best-effort: never fail the
    # analysis response because a write hiccuped.
    try:
        db.add(
            OnPageAudit(
                project_id=payload.project_id,
                url=result.url,
                keywords=result.keywords,
                primary_keyword=result.primary_keyword,
                overall_score=result.score,
            )
        )
        await db.commit()
    except Exception:  # noqa: BLE001 - persistence is non-critical
        await db.rollback()

    return result
