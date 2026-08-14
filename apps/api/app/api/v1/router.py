"""Aggregates all v1 API route modules under a single router."""

from fastapi import APIRouter

from app.api.v1.routes import (
    agency,
    assistant,
    audits,
    auth,
    automation,
    backlinks,
    competitors,
    content,
    gap_analysis,
    health,
    internal_links,
    jobs,
    keywords,
    optimizer,
    projects,
    public,
    reports,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(audits.router, prefix="/audits", tags=["audit"])
api_router.include_router(
    keywords.router, prefix="/keywords", tags=["keywords"]
)
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(
    optimizer.router, prefix="/optimizer", tags=["optimizer"]
)
api_router.include_router(
    competitors.router, prefix="/competitors", tags=["competitors"]
)
api_router.include_router(
    gap_analysis.router, prefix="/gap-analysis", tags=["gap-analysis"]
)
api_router.include_router(
    internal_links.router, prefix="/internal-links", tags=["internal-links"]
)
api_router.include_router(
    backlinks.router, prefix="/backlinks", tags=["backlinks"]
)
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(
    assistant.router, prefix="/assistant", tags=["assistant"]
)
api_router.include_router(
    automation.router, prefix="/automation", tags=["automation"]
)
api_router.include_router(agency.router, prefix="/agency", tags=["agency"])
api_router.include_router(
    agency.invite_router, prefix="/invites", tags=["agency"]
)
api_router.include_router(public.router, prefix="/public", tags=["public"])
