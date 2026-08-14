"""Automation service.

Implements the scheduled automations and their email notifications:
  - Daily: broken-link monitoring (alert on NEW broken links) and rank-drop
    detection (alert when a tracked keyword drops > RANK_DROP_THRESHOLD).
  - Weekly: audit re-run, competitor content-change detection (weekly diff),
    and a weekly summary email.

Each project is processed independently and best-effort, so one failing
project/site never aborts the batch. `run_daily`/`run_weekly` accept an
optional project_id for on-demand ("run now") execution.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit import AuditReport
from app.models.automation import AutomationSettings
from app.models.content import Content
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.user import User
from app.services import (
    audit_service,
    backlink_service,
    competitor_service,
    email_service,
)

logger = logging.getLogger(__name__)


def _homepage(project: Project) -> str:
    domain = project.domain
    return domain if urlparse(domain).scheme else f"https://{domain}"


async def _targets(
    db: AsyncSession, project_id: uuid.UUID | None
) -> list[tuple[AutomationSettings, Project, str]]:
    stmt = (
        select(AutomationSettings, Project, User.email)
        .join(Project, AutomationSettings.project_id == Project.id)
        .join(User, Project.owner_id == User.id)
    )
    if project_id is not None:
        stmt = stmt.where(AutomationSettings.project_id == project_id)
    return list((await db.execute(stmt)).all())


# --- Daily ---------------------------------------------------------------
async def run_daily(db: AsyncSession, project_id: uuid.UUID | None = None) -> int:
    processed = 0
    for s, project, owner_email in await _targets(db, project_id):
        email_to = s.notification_email or owner_email
        if s.broken_link_monitoring:
            try:
                await _broken_link_check(s, project, email_to)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Broken-link check failed for %s: %s", project.domain, exc)
        processed += 1
    await db.commit()
    logger.info("Daily automations processed %d project(s)", processed)
    return processed


async def _broken_link_check(
    s: AutomationSettings, project: Project, email_to: str
) -> None:
    url = s.monitor_url or _homepage(project)
    report = await backlink_service.find_broken_links(url)
    current = sorted({link.url for link in report.broken_links})
    previous = set(s.last_broken_links or [])
    new_broken = [u for u in current if u not in previous]
    s.last_broken_links = current

    if new_broken and s.email_notifications and s.notify_broken_links:
        items = "".join(f"<li>{u}</li>" for u in new_broken)
        html = (
            f"<h2>New broken links on {project.name}</h2>"
            f"<p>{len(new_broken)} new broken link(s) found on "
            f'<a href="{url}">{url}</a>:</p><ul>{items}</ul>'
        )
        await email_service.send_email(
            email_to,
            f"[{project.name}] {len(new_broken)} new broken link(s)",
            html,
        )


# --- Weekly --------------------------------------------------------------
async def run_weekly(db: AsyncSession, project_id: uuid.UUID | None = None) -> int:
    processed = 0
    for s, project, owner_email in await _targets(db, project_id):
        email_to = s.notification_email or owner_email
        if s.weekly_audit:
            try:
                await _weekly_audit(db, s, project)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Weekly audit failed for %s: %s", project.domain, exc)

        changed_competitors: list[str] = []
        if s.competitor_monitoring:
            try:
                changed_competitors = await _competitor_diff(s, project)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Competitor diff failed for %s: %s", project.domain, exc)

        if s.weekly_summary and s.email_notifications:
            try:
                await _weekly_summary(db, project, email_to, changed_competitors)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Weekly summary failed for %s: %s", project.domain, exc)
        processed += 1
    await db.commit()
    logger.info("Weekly automations processed %d project(s)", processed)
    return processed


async def _weekly_audit(
    db: AsyncSession, s: AutomationSettings, project: Project
) -> None:
    url = s.audit_url or _homepage(project)
    results, score = await audit_service.run_audit(url)
    db.add(
        AuditReport(
            project_id=project.id,
            url=url,
            status="completed",
            score=score,
            results=results.model_dump(),
            completed_at=datetime.now(timezone.utc),
        )
    )


async def _competitor_diff(
    s: AutomationSettings, project: Project
) -> list[str]:
    hashes = dict(s.competitor_hashes or {})
    changed: list[str] = []
    for url in s.competitor_urls or []:
        try:
            profile = await competitor_service.crawl_site(url, max_pages=5)
        except Exception:  # noqa: BLE001
            continue
        signature = " ".join(profile.sample_titles + profile.top_headings)
        digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        if url in hashes and hashes[url] != digest:
            changed.append(url)
        hashes[url] = digest
    s.competitor_hashes = hashes
    return changed


async def _weekly_summary(
    db: AsyncSession,
    project: Project,
    email_to: str,
    changed_competitors: list[str],
) -> None:
    audit = (
        await db.execute(
            select(AuditReport)
            .where(
                AuditReport.project_id == project.id,
                AuditReport.status == "completed",
            )
            .order_by(AuditReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    async def count(model) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).where(model.project_id == project.id)
                )
            ).scalar_one()
        )

    score = audit.score if audit else "—"
    competitors_html = (
        "<p><strong>Competitor changes detected:</strong> "
        + ", ".join(changed_competitors)
        + "</p>"
        if changed_competitors
        else ""
    )
    html = (
        f"<h2>Weekly SEO summary — {project.name}</h2>"
        f"<p>{project.domain}</p>"
        f"<ul>"
        f"<li>Latest audit score: <strong>{score}</strong></li>"
        f"<li>Keywords tracked/researched: {await count(Keyword)}</li>"
        f"<li>Content pieces: {await count(Content)}</li>"
        f"</ul>{competitors_html}"
        "<p>Log in to RankPilot AI for the full report.</p>"
    )
    await email_service.send_email(
        email_to, f"[{project.name}] Weekly SEO summary", html
    )
