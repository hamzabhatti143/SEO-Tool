"""Fix orchestration service (Core Web Vitals auto-fixes).

Orchestrates applying and reverting automated CWV fixes across platforms:

  1. Read the project's ``platform`` and route to the matching handler.
  2. The handler applies (or reverts) fixes on the connected site and returns a
     revertible ``external_change_id`` plus before/after snapshots.
  3. Re-scan the page (shared write path with the scan endpoint) so we capture
     the CWV score after the change and store a fresh ``CoreWebVitals`` row.
  4. Record a ``ChangeLog`` row tying it all together.

The platform handlers are **stubbed** for now (mock responses) — see the TODOs
in each. They'll be implemented once the WordPress plugin and Shopify app
expose their fix/revert endpoints, without changing this orchestration flow.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_log import ChangeLog
from app.models.core_web_vitals import CoreWebVitals
from app.models.project import Project
from app.services import core_web_vitals_service
from app.services.core_web_vitals_service import CoreWebVitalsError


class FixError(Exception):
    """Raised when a fix/revert cannot be orchestrated (bad platform, etc.)."""


@dataclass
class FixHandlerResult:
    """What a platform handler returns after applying/reverting a change."""

    external_change_id: str | None
    issue_type: str = "core_web_vitals"
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    detail: str | None = None


@dataclass
class OrchestrationResult:
    change: ChangeLog
    new_scan: CoreWebVitals | None
    rescan_status: str  # completed | failed | skipped
    detail: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Platform handlers — STUBBED. Replace the mock bodies with real calls.
# ---------------------------------------------------------------------------


async def _wordpress_fix_all(
    db: AsyncSession, project: Project, url: str
) -> FixHandlerResult:
    # TODO(connectors): call the RankPilot WordPress plugin's fix endpoint
    #   (e.g. POST {site}/wp-json/rankpilot/v1/fixes) with the project's
    #   decrypted API key. The plugin should apply CWV fixes (add width/height
    #   to images, defer non-critical JS, preload the LCP image, set
    #   font-display, purge unused CSS) and return a change id we can revert.
    return FixHandlerResult(
        external_change_id=f"wp-change-{uuid.uuid4().hex[:12]}",
        before_snapshot={"mock": True, "note": "plugin captures the prior state"},
        after_snapshot={
            "mock": True,
            "fixes_applied": [
                "unsized_images",
                "font_display_missing",
                "render_blocking_resources",
            ],
        },
        detail="STUB: WordPress fix handler not implemented — returned a mock.",
    )


async def _shopify_fix_all(
    db: AsyncSession, project: Project, url: str
) -> FixHandlerResult:
    # TODO(connectors): using the stored Shopify Admin API token, duplicate the
    #   live theme as a backup (that backup's theme id is the revert handle),
    #   then patch theme assets to fix CWV issues (lazy-load below-the-fold
    #   images, add image dimensions, preconnect, defer apps). Return the
    #   backup theme id as external_change_id.
    return FixHandlerResult(
        external_change_id=f"shopify-theme-backup-{uuid.uuid4().hex[:10]}",
        before_snapshot={"mock": True, "note": "live theme duplicated as backup"},
        after_snapshot={
            "mock": True,
            "fixes_applied": ["lazy_load_images", "unsized_images", "preconnect"],
        },
        detail="STUB: Shopify fix handler not implemented — returned a mock.",
    )


async def _wordpress_revert(
    db: AsyncSession, project: Project, change: ChangeLog
) -> FixHandlerResult:
    # TODO(connectors): call the plugin revert endpoint with
    #   change.external_change_id to roll back that change set.
    return FixHandlerResult(
        external_change_id=change.external_change_id,
        issue_type=change.issue_type,
        before_snapshot=change.after_snapshot,
        after_snapshot=change.before_snapshot,
        detail="STUB: WordPress revert handler not implemented — returned a mock.",
    )


async def _shopify_revert(
    db: AsyncSession, project: Project, change: ChangeLog
) -> FixHandlerResult:
    # TODO(connectors): publish the backup theme identified by
    #   change.external_change_id to restore the pre-fix state.
    return FixHandlerResult(
        external_change_id=change.external_change_id,
        issue_type=change.issue_type,
        before_snapshot=change.after_snapshot,
        after_snapshot=change.before_snapshot,
        detail="STUB: Shopify revert handler not implemented — returned a mock.",
    )


_FIX_HANDLERS = {
    "wordpress": _wordpress_fix_all,
    "shopify": _shopify_fix_all,
}
_REVERT_HANDLERS = {
    "wordpress": _wordpress_revert,
    "shopify": _shopify_revert,
}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def apply_fix_all(
    db: AsyncSession, project: Project, url: str
) -> OrchestrationResult:
    """Apply all CWV fixes for a project, then re-scan and record the change."""
    handler = _FIX_HANDLERS.get(project.platform)
    if handler is None:
        raise FixError(
            f"Project platform '{project.platform}' cannot be auto-fixed. "
            "Connect a WordPress or Shopify site first."
        )

    # Baseline score/snapshot from the most recent scan of this page.
    baseline = await _latest_scan(db, project.id, url)
    cwv_before = baseline.performance_score if baseline else None

    result = await handler(db, project, url)

    new_scan, rescan_status, detail = await _rescan(db, project.id, url)
    cwv_after = new_scan.performance_score if new_scan else None

    change = ChangeLog(
        project_id=project.id,
        platform=project.platform,
        issue_type=result.issue_type,
        external_change_id=result.external_change_id,
        before_snapshot=result.before_snapshot,
        after_snapshot=result.after_snapshot,
        cwv_score_before=cwv_before,
        cwv_score_after=cwv_after,
        applied_at=datetime.now(timezone.utc),
        status="applied",
    )
    db.add(change)
    await db.commit()
    await db.refresh(change)

    return OrchestrationResult(
        change=change,
        new_scan=new_scan,
        rescan_status=rescan_status,
        detail=detail or result.detail,
    )


async def revert_fix(
    db: AsyncSession, project: Project, change: ChangeLog
) -> OrchestrationResult:
    """Revert a previously applied change, then re-scan and record the result."""
    if change.status == "reverted":
        raise FixError("This change has already been reverted.")

    handler = _REVERT_HANDLERS.get(project.platform)
    if handler is None:
        raise FixError(
            f"Project platform '{project.platform}' cannot be reverted."
        )

    result = await handler(db, project, change)

    url = await _url_for_project(db, project)
    new_scan, rescan_status, detail = await _rescan(db, project.id, url)

    change.status = "reverted"
    # Record the post-revert score so the row reflects the current state.
    if new_scan is not None:
        change.cwv_score_after = new_scan.performance_score
    db.add(change)
    await db.commit()
    await db.refresh(change)

    return OrchestrationResult(
        change=change,
        new_scan=new_scan,
        rescan_status=rescan_status,
        detail=detail or result.detail,
    )


async def resolve_target_url(
    db: AsyncSession, project: Project, requested: str | None
) -> str:
    """Pick which URL to fix + re-scan: explicit → latest scan → domain."""
    if requested:
        return requested
    latest = await _latest_scan(db, project.id, None)
    if latest is not None:
        return latest.url
    return await _url_for_project(db, project)


# --- internals -------------------------------------------------------------


async def _rescan(
    db: AsyncSession, project_id: uuid.UUID, url: str
) -> tuple[CoreWebVitals | None, str, str | None]:
    """Best-effort re-scan: never fail the fix if the scan can't run."""
    try:
        scan = await core_web_vitals_service.scan_and_store(db, project_id, url)
    except CoreWebVitalsError as exc:
        return None, "failed", f"Fix applied, but the re-scan failed: {exc}"
    return scan, "completed", None


async def _latest_scan(
    db: AsyncSession, project_id: uuid.UUID, url: str | None
) -> CoreWebVitals | None:
    stmt = select(CoreWebVitals).where(CoreWebVitals.project_id == project_id)
    if url is not None:
        stmt = stmt.where(CoreWebVitals.url == url)
    stmt = stmt.order_by(CoreWebVitals.scanned_at.desc()).limit(1)
    return (await db.execute(stmt)).scalars().first()


async def _url_for_project(db: AsyncSession, project: Project) -> str:
    domain = project.domain.strip()
    return domain if "://" in domain else f"https://{domain}"
