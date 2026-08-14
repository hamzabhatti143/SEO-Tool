"""Backlink Center routes.

`POST /profile` returns basic backlink data for a domain from a free-tier
provider (OpenLinkProfiler by default) — referring domains, anchor
distribution, follow/nofollow ratio. `POST /broken-links` crawls a page and
flags broken outbound links for broken-link-building outreach.

Authenticated; stateless. Free data is limited — a paid provider key
(Ahrefs/Semrush) can be configured later for full data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app import tasks
from app.api.deps import get_current_user
from app.core.queue import dispatch, get_arq_optional
from app.models.user import User
from app.schemas.backlinks import BacklinkProfileRequest, BacklinkProfileResponse
from app.schemas.backlinks import BrokenLinkRequest
from app.schemas.jobs import JobEnqueued
from app.services import backlink_service

router = APIRouter()


@router.post("/profile", response_model=BacklinkProfileResponse)
async def backlink_profile(
    payload: BacklinkProfileRequest,
    _current_user: User = Depends(get_current_user),
) -> BacklinkProfileResponse:
    """Fetch and aggregate basic backlink data for a domain (fast, inline)."""
    return await backlink_service.get_profile(payload.domain)


@router.post(
    "/broken-links",
    response_model=JobEnqueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def broken_links(
    payload: BrokenLinkRequest,
    _current_user: User = Depends(get_current_user),
    arq=Depends(get_arq_optional),
) -> JobEnqueued:
    """Enqueue a broken-link crawl (heavy). Poll /jobs/{id} for the result."""
    job_id = await dispatch(
        arq, "task_find_broken_links", tasks.task_find_broken_links, payload.url
    )
    return JobEnqueued(job_id=job_id)
