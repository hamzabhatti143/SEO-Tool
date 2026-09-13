"""Automation service.

Runs the scheduled automations and emails a report when a run completes:
  - Daily: a COMPLETE re-run — full site audit, broken-link monitoring,
    competitor content diff, and content/keyword stats — emailed as one report.
  - Weekly: the same audit re-run, competitor content-change detection, and
    content/keyword stats (gated by the per-project weekly toggles).

When a run finishes for a project, a single well-formatted **Automation
Report** email is sent to the owner — but only for **Premium** accounts (the
Automation module is Premium-only) that have email notifications enabled.

Each project is processed independently and best-effort, so one failing
project/site never aborts the batch. `run_daily`/`run_weekly` accept an
optional project_id for on-demand ("run now") execution.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import feature_flags
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
) -> list[tuple[AutomationSettings, Project, str, str]]:
    stmt = (
        select(AutomationSettings, Project, User.email, User.plan)
        .join(Project, AutomationSettings.project_id == Project.id)
        .join(User, Project.owner_id == User.id)
    )
    if project_id is not None:
        stmt = stmt.where(AutomationSettings.project_id == project_id)
    return list((await db.execute(stmt)).all())


# --- Daily ---------------------------------------------------------------
async def run_daily(db: AsyncSession, project_id: uuid.UUID | None = None) -> int:
    """Perform a COMPLETE re-run per project and email the full report.

    A daily run now re-runs the whole pipeline — full site audit, broken-link
    check, competitor content diff, and content/keyword stats — then sends one
    comprehensive Automation Report. Each section is best-effort so a single
    failure never blocks the rest of the report or the batch.
    """
    processed = 0
    for s, project, owner_email, owner_plan in await _targets(db, project_id):
        email_to = s.notification_email or owner_email
        sections: list[str] = []

        # 1. Full site audit (the core re-run).
        try:
            sections.append(await _audit_section(db, s, project))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Daily audit failed for %s: %s", project.domain, exc)

        # 2. Broken-link monitoring.
        try:
            sections.append(await _broken_link_section(s, project))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Broken-link check failed for %s: %s", project.domain, exc
            )

        # 3. Competitor content diff (only when competitors are configured).
        if s.competitor_urls:
            try:
                sections.append(await _competitor_section(s, project))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Competitor diff failed for %s: %s", project.domain, exc
                )

        # 4. Content & keyword stats.
        try:
            sections.append(await _stats_section(db, project))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Stats section failed for %s: %s", project.domain, exc
            )

        await _maybe_send_report(
            project, email_to, owner_plan, s, "Daily", sections
        )
        processed += 1
    await db.commit()
    logger.info("Daily automations processed %d project(s)", processed)
    return processed


async def _broken_link_section(s: AutomationSettings, project: Project) -> str:
    """Run the broken-link check, update state, and return an HTML section."""
    url = s.monitor_url or _homepage(project)
    report = await backlink_service.find_broken_links(url)
    current = sorted({link.url for link in report.broken_links})
    previous = set(s.last_broken_links or [])
    new_broken = {u for u in current if u not in previous}
    s.last_broken_links = current

    link = f'<a href="{url}" style="color:#4f46e5">{url}</a>'
    if report.broken_links:
        rows = "".join(
            _broken_row(b, b.url in new_broken) for b in report.broken_links[:20]
        )
        more = (
            f"<p style='color:#64748b'>…and {report.broken_count - 20} more.</p>"
            if report.broken_count > 20
            else ""
        )
        new_note = f" ({len(new_broken)} new)" if new_broken else ""
        body = (
            f'<p><strong style="color:#dc2626">{report.broken_count} broken '
            f"link(s)</strong>{new_note} found out of {report.links_checked} "
            f"checked on {link}:</p>"
            f"<ul style='padding-left:18px;margin:6px 0'>{rows}</ul>{more}"
        )
    else:
        body = (
            f"✅ No broken links — checked {report.links_checked} link(s) "
            f"on {link}."
        )
    return _section("Broken-link monitoring", body)


def _broken_row(b, is_new: bool) -> str:
    status = b.status_code if b.status_code else (b.reason or "error")
    new_tag = (
        " <span style='color:#dc2626;font-weight:600'>(new)</span>"
        if is_new
        else ""
    )
    anchor = f" — “{b.anchor}”" if b.anchor else ""
    return (
        "<li style='margin:2px 0'>"
        f'<a href="{b.url}" style="color:#4f46e5">{b.url}</a> '
        f"<span style='color:#64748b'>[{status}]</span>{new_tag}"
        f"<span style='color:#94a3b8'>{anchor}</span></li>"
    )


# --- Weekly --------------------------------------------------------------
async def run_weekly(db: AsyncSession, project_id: uuid.UUID | None = None) -> int:
    processed = 0
    for s, project, owner_email, owner_plan in await _targets(db, project_id):
        email_to = s.notification_email or owner_email
        sections: list[str] = []

        if s.weekly_audit:
            try:
                sections.append(await _audit_section(db, s, project))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Weekly audit failed for %s: %s", project.domain, exc
                )
        if s.competitor_monitoring:
            try:
                sections.append(await _competitor_section(s, project))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Competitor diff failed for %s: %s", project.domain, exc
                )
        try:
            sections.append(await _stats_section(db, project))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Stats section failed for %s: %s", project.domain, exc)

        await _maybe_send_report(
            project, email_to, owner_plan, s, "Weekly", sections
        )
        processed += 1
    await db.commit()
    logger.info("Weekly automations processed %d project(s)", processed)
    return processed


async def _audit_section(
    db: AsyncSession, s: AutomationSettings, project: Project
) -> str:
    url = s.audit_url or _homepage(project)
    results, score = await audit_service.run_audit(url)
    db.add(
        AuditReport(
            project_id=project.id,
            url=url,
            status="completed",
            score=score,
            results=results.model_dump(),
            completed_at=datetime.now(UTC),
        )
    )
    issues = results.issues
    label, color = _score_label(score)
    body = (
        f'<p>Audited <a href="{url}" style="color:#4f46e5">{url}</a>.</p>'
        f'<p style="font-size:22px;font-weight:700;color:{color};margin:4px 0">'
        f"{score}/100 <span style='font-size:13px;font-weight:600'>"
        f"({label})</span></p>"
    )
    if issues:
        # Show critical → warning → info, listing each issue with its fix.
        ordered = sorted(issues, key=lambda i: _SEVERITY_ORDER.get(_sev(i), 3))
        rows = "".join(_issue_row(i) for i in ordered[:20])
        more = (
            f"<p style='color:#64748b'>…and {len(issues) - 20} more.</p>"
            if len(issues) > 20
            else ""
        )
        body += (
            f"<p style='color:#334155'>{len(issues)} issue(s) flagged in this "
            f"scan:</p><ul style='padding-left:18px;margin:6px 0'>{rows}</ul>"
            f"{more}"
        )
    else:
        body += "<p style='color:#059669'>✅ No issues flagged in this scan.</p>"
    return _section("Website audit", body)


_SEVERITY_COLOR = {"critical": "#dc2626", "warning": "#d97706", "info": "#0284c7"}
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _sev(issue) -> str:
    """Severity as a plain lowercase string (handles str-enum or str)."""
    return str(getattr(issue.severity, "value", issue.severity)).lower()


def _issue_row(issue) -> str:
    sev = _sev(issue)
    color = _SEVERITY_COLOR.get(sev, "#64748b")
    return (
        "<li style='margin:6px 0'>"
        f"<span style='font-size:11px;font-weight:700;text-transform:uppercase;"
        f"color:{color}'>{sev}</span> "
        f"<span style='color:#0f172a'>{issue.message}</span>"
        f"<div style='color:#64748b;font-size:13px;margin-top:1px'>"
        f"{issue.recommendation}</div></li>"
    )


async def _competitor_section(s: AutomationSettings, project: Project) -> str:
    changed = await _competitor_diff(s, project)
    monitored = len(s.competitor_urls or [])
    if changed:
        items = "".join(
            f'<li style="margin:2px 0"><a href="{u}" style="color:#4f46e5">'
            f"{u}</a></li>"
            for u in changed
        )
        body = (
            f"<p><strong>{len(changed)} of {monitored}</strong> monitored "
            f"competitor(s) changed their content this week:</p>"
            f"<ul style='padding-left:18px;margin:6px 0'>{items}</ul>"
        )
    else:
        body = (
            f"No content changes detected across {monitored} monitored "
            f"competitor(s) this week."
        )
    return _section("Competitor monitoring", body)


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


async def _stats_section(db: AsyncSession, project: Project) -> str:
    async def count(model) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).where(model.project_id == project.id)
                )
            ).scalar_one()
        )

    body = (
        "<table style='width:100%;border-collapse:collapse;font-size:14px'>"
        f"<tr><td style='padding:6px 0;color:#64748b'>Keywords</td>"
        f"<td style='padding:6px 0;text-align:right;font-weight:600'>"
        f"{await count(Keyword)}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#64748b'>Content pieces</td>"
        f"<td style='padding:6px 0;text-align:right;font-weight:600'>"
        f"{await count(Content)}</td></tr>"
        "</table>"
    )
    return _section("Content & keywords", body)


# --- Report email --------------------------------------------------------
def _score_label(score: float | int | None) -> tuple[str, str]:
    if score is None:
        return "n/a", "#64748b"
    if score >= 80:
        return "healthy", "#059669"
    if score >= 50:
        return "needs work", "#d97706"
    return "poor", "#dc2626"


def _section(title: str, body_html: str) -> str:
    return (
        "<div style='margin-bottom:22px'>"
        f"<h3 style='margin:0 0 8px;font-size:15px;color:#0f172a'>{title}</h3>"
        f"<div style='font-size:14px;color:#334155;line-height:1.5'>"
        f"{body_html}</div></div>"
    )


def _report_html(project: Project, kind: str, sections: list[str]) -> str:
    when = datetime.now(UTC).strftime("%b %d, %Y")
    dashboard = f"{settings.FRONTEND_URL.rstrip('/')}/dashboard"
    inner = (
        f"<p style='margin:0 0 4px;font-size:16px;font-weight:600;color:#0f172a'>"
        f"{project.name}</p>"
        f"<p style='margin:0 0 20px;color:#64748b;font-size:13px'>"
        f"{project.domain} · {kind} run · {when}</p>"
        + "".join(sections)
        + f"<a href='{dashboard}' style='display:inline-block;background:#4f46e5;"
        "color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;"
        "font-size:14px;font-weight:600;margin-top:4px'>Open dashboard</a>"
    )
    return (
        "<div style='font-family:system-ui,-apple-system,Segoe UI,Arial,"
        "sans-serif;background:#f1f5f9;padding:24px'>"
        "<div style='max-width:600px;margin:0 auto;background:#fff;"
        "border-radius:12px;overflow:hidden;border:1px solid #e2e8f0'>"
        "<div style='background:#4f46e5;padding:20px 24px'>"
        "<div style='color:#fff;font-size:18px;font-weight:700'>RankPilot "
        "<span style='color:#c7d2fe'>AI</span></div>"
        "<div style='color:#e0e7ff;font-size:13px;margin-top:2px'>"
        "Automation Report</div></div>"
        f"<div style='padding:24px'>{inner}</div>"
        "<div style='padding:16px 24px;border-top:1px solid #e2e8f0;"
        "color:#94a3b8;font-size:12px'>You're receiving this because "
        "automation is enabled for this project. Manage it under "
        "Automation in your dashboard.</div></div></div>"
    )


async def _maybe_send_report(
    project: Project,
    email_to: str,
    owner_plan: str,
    s: AutomationSettings,
    kind: str,
    sections: list[str],
) -> None:
    """Email the run report — Premium accounts with notifications on only."""
    if not sections or not email_to:
        return
    if not s.email_notifications:
        return
    # Automation (and its reports) are a Premium-only feature.
    if not feature_flags.tier_allows(owner_plan, "automation"):
        return
    html = _report_html(project, kind, sections)
    await email_service.send_email(
        email_to, f"[{project.name}] {kind} automation report", html
    )
