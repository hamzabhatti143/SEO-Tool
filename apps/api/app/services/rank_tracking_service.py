"""Rank Tracking service.

Queries SerpApi for each tracked keyword and stores a daily snapshot
(date, position, url). Used by both the APScheduler cron (`track_all`) and
the on-demand refresh endpoint (`track_project`).
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.rank_tracking import RankSnapshot, TrackedKeyword
from app.schemas.rank_tracking import (
    KeywordHistory,
    RankHistoryResponse,
    RankSnapshotRead,
    TrackedKeywordRead,
)
from app.services import serpapi_service

logger = logging.getLogger(__name__)


async def _track_one(
    db: AsyncSession, tk: TrackedKeyword, domain: str
) -> None:
    """Check one keyword and upsert today's snapshot (does not commit)."""
    position, url = await serpapi_service.check_rank(tk.keyword, domain)
    today = date.today()
    existing = (
        await db.execute(
            select(RankSnapshot).where(
                RankSnapshot.tracked_keyword_id == tk.id,
                RankSnapshot.checked_on == today,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.position = position
        existing.url = url
    else:
        db.add(
            RankSnapshot(
                tracked_keyword_id=tk.id,
                checked_on=today,
                position=position,
                url=url,
            )
        )


async def track_project(db: AsyncSession, project: Project) -> int:
    """Check every tracked keyword for one project. Returns count checked."""
    keywords = list(
        (
            await db.execute(
                select(TrackedKeyword).where(
                    TrackedKeyword.project_id == project.id
                )
            )
        ).scalars()
    )
    checked = 0
    for tk in keywords:
        try:
            await _track_one(db, tk, project.domain)
            checked += 1
        except Exception as exc:  # noqa: BLE001 - per-keyword best-effort
            logger.warning("Rank check failed for %r: %s", tk.keyword, exc)
    await db.commit()
    return checked


async def track_all(db: AsyncSession) -> int:
    """Check every tracked keyword across all projects (cron entrypoint)."""
    rows = (
        await db.execute(
            select(TrackedKeyword, Project.domain).join(
                Project, TrackedKeyword.project_id == Project.id
            )
        )
    ).all()
    checked = 0
    for tk, domain in rows:
        try:
            await _track_one(db, tk, domain)
            checked += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rank check failed for %r: %s", tk.keyword, exc)
    await db.commit()
    logger.info("Rank tracking job checked %d keyword(s)", checked)
    return checked


def _to_read(tk: TrackedKeyword) -> TrackedKeywordRead:
    latest = max(tk.snapshots, key=lambda s: s.checked_on, default=None)
    return TrackedKeywordRead(
        id=tk.id,
        project_id=tk.project_id,
        keyword=tk.keyword,
        created_at=tk.created_at,
        latest_position=latest.position if latest else None,
        latest_url=latest.url if latest else None,
        latest_checked_on=latest.checked_on if latest else None,
    )


async def list_tracked(
    db: AsyncSession, project: Project
) -> list[TrackedKeywordRead]:
    keywords = list(
        (
            await db.execute(
                select(TrackedKeyword)
                .where(TrackedKeyword.project_id == project.id)
                .options(selectinload(TrackedKeyword.snapshots))
                .order_by(TrackedKeyword.created_at)
            )
        ).scalars()
    )
    return [_to_read(tk) for tk in keywords]


async def get_history(
    db: AsyncSession, project: Project
) -> RankHistoryResponse:
    keywords = list(
        (
            await db.execute(
                select(TrackedKeyword)
                .where(TrackedKeyword.project_id == project.id)
                .options(selectinload(TrackedKeyword.snapshots))
                .order_by(TrackedKeyword.created_at)
            )
        ).scalars()
    )
    history = [
        KeywordHistory(
            id=tk.id,
            keyword=tk.keyword,
            snapshots=[
                RankSnapshotRead.model_validate(s)
                for s in sorted(tk.snapshots, key=lambda s: s.checked_on)
            ],
        )
        for tk in keywords
    ]
    return RankHistoryResponse(
        serpapi_configured=serpapi_service.is_configured(), keywords=history
    )
