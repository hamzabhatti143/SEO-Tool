"""On-Page SEO Optimizer routes.

Stateless analysis: takes a URL + target keyword and returns a scored,
categorized on-page report. Requires authentication but is not tied to a
project (nothing is persisted).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.optimizer import OptimizeRequest, OptimizeResponse
from app.services import optimizer_service

router = APIRouter()


@router.post("/analyze", response_model=OptimizeResponse)
async def analyze_on_page(
    payload: OptimizeRequest,
    _current_user: User = Depends(get_current_user),
) -> OptimizeResponse:
    """Analyze a page against a target keyword and return a scored report."""
    try:
        return await optimizer_service.analyze(payload)
    except Exception as exc:  # noqa: BLE001 - surface crawl/analysis failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"On-page analysis failed: {exc}",
        ) from exc
