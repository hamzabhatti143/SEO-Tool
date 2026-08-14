"""ARQ task functions and cron entrypoints.

These run in the worker process (app.worker). Heavy crawls/AI calls are
enqueued from the web layer (ownership already checked there) and executed
here off the request path. Cron entrypoints run scheduled automations.

Each task returns a JSON-serializable dict so the result can be read back
via GET /jobs/{id}. Stateful tasks (audit, internal-link crawl) persist to
the DB and return an id/summary; stateless tasks return the full payload.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.base import AsyncSessionLocal
from app.models.audit import AuditReport
from app.models.keyword import Keyword
from app.models.project import Project
from app.schemas.keyword import KeywordRead, KeywordResearchRequest
from app.services import (
    audit_service,
    automation_service,
    backlink_service,
    competitor_service,
    gap_analysis_service,
    internal_link_service,
    keyword_service,
)
from app.services.project_summary import build_user_summary


async def task_research_keywords(
    ctx: dict, project_id: str, seed_keyword: str
) -> list[dict[str, Any]]:
    """Run keyword research (OpenAI + clustering + trends), persist, and
    return the rows. Slow (~30s), so it runs here off the request path."""
    request = KeywordResearchRequest(
        project_id=uuid.UUID(project_id), seed_keyword=seed_keyword
    )
    keywords = await keyword_service.research_keywords(request)
    async with AsyncSessionLocal() as db:
        rows = [
            Keyword(
                project_id=uuid.UUID(project_id),
                seed_keyword=seed_keyword,
                term=item.term,
                kind=item.kind,
                difficulty=item.difficulty,
                search_intent=item.search_intent,
                cluster_id=item.cluster_id,
                cluster_label=item.cluster_label,
                trend_score=item.trend_score,
                trend_direction=item.trend_direction,
            )
            for item in keywords
        ]
        db.add_all(rows)
        await db.commit()
        for row in rows:
            await db.refresh(row)
        return [
            KeywordRead.model_validate(row).model_dump(mode="json")
            for row in rows
        ]


# --- Heavy, request-triggered tasks -------------------------------------
async def task_run_audit(ctx: dict, project_id: str, url: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        audit = AuditReport(
            project_id=uuid.UUID(project_id), url=url, status="running"
        )
        db.add(audit)
        await db.flush()
        try:
            results, score = await audit_service.run_audit(url)
        except Exception as exc:  # noqa: BLE001
            audit.status = "failed"
            audit.results = {"error": str(exc)}
            audit.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise
        audit.status = "completed"
        audit.score = score
        audit.results = results.model_dump()
        audit.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(audit)
        return {"audit_id": str(audit.id), "score": score}


async def task_crawl_internal_links(
    ctx: dict, project_id: str
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, uuid.UUID(project_id))
        if project is None:
            raise RuntimeError("Project not found")
        pages = await internal_link_service.crawl_and_store(db, project)
        return {"pages_crawled": len(pages)}


async def task_analyze_competitor(
    ctx: dict, project_id: str, competitor_url: str
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, uuid.UUID(project_id))
        if project is None:
            raise RuntimeError("Project not found")
        summary = await build_user_summary(db, project)
    report = await competitor_service.analyze(competitor_url, summary)
    return report.model_dump()


async def task_analyze_gaps(
    ctx: dict, project_id: str, competitor_urls: list[str]
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, uuid.UUID(project_id))
        if project is None:
            raise RuntimeError("Project not found")
        summary = await build_user_summary(db, project)
    response = await gap_analysis_service.analyze(competitor_urls, summary)
    return response.model_dump()


async def task_find_broken_links(ctx: dict, url: str) -> dict[str, Any]:
    report = await backlink_service.find_broken_links(url)
    return report.model_dump()


# --- Cron entrypoints (scheduled in app.worker) -------------------------
async def cron_automation_daily(ctx: dict) -> None:
    async with AsyncSessionLocal() as db:
        await automation_service.run_daily(db)


async def cron_automation_weekly(ctx: dict) -> None:
    async with AsyncSessionLocal() as db:
        await automation_service.run_weekly(db)
