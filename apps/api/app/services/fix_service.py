"""Fix orchestration service (Core Web Vitals auto-fixes).

Orchestrates applying and reverting automated CWV fixes across platforms:

  1. Read the project's ``platform`` and route to the matching handler.
  2. The handler applies (or reverts) fixes on the connected site and returns a
     revertible ``external_change_id`` plus before/after snapshots.
  3. Re-scan the page (shared write path with the scan endpoint) so we capture
     the CWV score after the change and store a fresh ``CoreWebVitals`` row.
  4. Record a ``ChangeLog`` row tying it all together.

The **WordPress** handler is implemented against the RankPilot Connector
plugin's fix engine (POST /wp-json/rankpilot/v1/{snapshot,apply-fix,revert}).
The **Shopify** handler is still stubbed (mock responses) until the Shopify app
exposes its endpoints — the orchestration flow is identical for both.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import InvalidToken, decrypt
from app.models.change_log import ChangeLog
from app.models.core_web_vitals import CoreWebVitals
from app.models.project import Project
from app.services import connector_service, core_web_vitals_service
from app.services.core_web_vitals_service import CoreWebVitalsError

# Maps a Lighthouse audit id (as stored in a scan's insights/diagnostics) to
# the plugin fix type that addresses it. lazy_load has no direct audit — it's
# added when the page has image issues, and as a safe fallback.
_AUDIT_TO_FIX: dict[str, str] = {
    "unsized-images": "image_dimensions",
    "uses-optimized-images": "image_compression",
    "modern-image-formats": "image_compression",
    "font-display": "font_display",
    "render-blocking-resources": "defer_css",
}
_IMAGE_AUDITS = frozenset(
    {
        "unsized-images",
        "uses-optimized-images",
        "modern-image-formats",
        "offscreen-images",
    }
)
_WORDPRESS_FALLBACK_FIX = "lazy_load"
# Bound the number of plugin round-trips (and image snapshots) per fix-all.
_WORDPRESS_MAX_FIXES = 12
_WORDPRESS_MAX_IMAGES = 3


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
# WordPress handler — real calls to the RankPilot Connector plugin
# ---------------------------------------------------------------------------


async def _wp_credentials(
    db: AsyncSession, project: Project
) -> tuple[str, str]:
    """Return (site_url, api_key) for the project's WordPress connection."""
    cred = await connector_service.get_credentials(db, project.id)
    if cred is None or cred.platform != "wordpress" or not cred.site_url:
        raise FixError(
            "No WordPress connection for this project. Connect the site first."
        )
    try:
        key = decrypt(cred.encrypted_api_key_or_token)
    except InvalidToken as exc:
        raise FixError(
            "Stored WordPress credentials could not be decrypted."
        ) from exc
    return cred.site_url.rstrip("/"), key


async def _wp_request(
    site_url: str,
    key: str,
    path: str,
    payload: dict[str, Any],
    ok_statuses: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    """POST to a plugin fix endpoint with the Bearer key; return parsed JSON."""
    namespace = settings.WORDPRESS_API_NAMESPACE.strip("/")
    endpoint = f"{site_url}/wp-json/{namespace}{path}"
    try:
        async with httpx.AsyncClient(
            timeout=settings.WORDPRESS_CONNECT_TIMEOUT
        ) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
            )
    except httpx.HTTPError as exc:
        raise FixError(f"Could not reach the WordPress plugin: {exc}") from exc

    if resp.status_code not in ok_statuses:
        detail = _wp_error_detail(resp)
        raise FixError(f"WordPress plugin error on {path}: {detail}")
    return resp.json()


def _wordpress_fix_plan(
    report: dict[str, Any] | None, page_url: str
) -> list[dict[str, str]]:
    """Turn a scan's detected performance audits into plugin fix instructions.

    Each instruction is ``{"change_type": ..., "target": ...}``. Falls back to a
    single safe lazy_load when there's no scan or no mappable issue.
    """
    audits: dict[str, dict[str, Any]] = {}
    perf = ((report or {}).get("categories") or {}).get("performance") or {}
    for group in ("insights", "diagnostics"):
        for item in perf.get(group) or []:
            if isinstance(item, dict) and item.get("id"):
                audits[item["id"]] = item

    plan: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(change_type: str, target: str) -> None:
        key = (change_type, target)
        if target and key not in seen:
            seen.add(key)
            plan.append({"change_type": change_type, "target": target})

    # Page-level content fixes.
    if "unsized-images" in audits:
        add("image_dimensions", page_url)
    if "font-display" in audits:
        # Best-effort: the theme's main stylesheet (the plugin no-ops if it has
        # no @font-face). Target is theme-relative and validated plugin-side.
        add("font_display", "style.css")

    # Per-image compression (bounded).
    image_count = 0
    for audit_id in ("uses-optimized-images", "modern-image-formats"):
        for src in audits.get(audit_id, {}).get("resource_urls") or []:
            if image_count >= _WORDPRESS_MAX_IMAGES:
                break
            add("image_compression", src)
            image_count += 1

    # Render-blocking stylesheets → defer (CSS only; JS defer isn't supported).
    for href in audits.get("render-blocking-resources", {}).get(
        "resource_urls"
    ) or []:
        if href.split("?", 1)[0].lower().endswith(".css"):
            add("defer_css", href)

    # Lazy-load below-the-fold images when the page has image issues.
    if audits.keys() & _IMAGE_AUDITS:
        add("lazy_load", page_url)

    if not plan:
        add(_WORDPRESS_FALLBACK_FIX, page_url)

    return plan[:_WORDPRESS_MAX_FIXES]


def _wp_error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return str(body.get("message") or body).strip()[:200]
    except ValueError:
        return f"HTTP {resp.status_code}"


async def _wordpress_fix_all(
    db: AsyncSession,
    project: Project,
    url: str,
    baseline: CoreWebVitals | None,
) -> FixHandlerResult:
    """Apply the fixes the scan's issues call for, via the plugin.

    Builds a plan from the baseline scan's detected audits (image_dimensions,
    image_compression, defer_css, font_display, lazy_load), then snapshot +
    apply-fix each. Records every plugin change id so the whole set is
    revertible.
    """
    site_url, key = await _wp_credentials(db, project)
    report = baseline.report_json if baseline is not None else None
    plan = _wordpress_fix_plan(report, url)

    applied: list[dict[str, Any]] = []
    errors: list[str] = []
    for instr in plan:
        change_type = instr["change_type"]
        target = instr["target"]
        try:
            snap = await _wp_request(
                site_url, key, "/snapshot",
                {"change_type": change_type, "target": target},
            )
            change_id = snap.get("change_id")
            if change_id is None:
                raise FixError("/snapshot did not return a change_id.")
            result = await _wp_request(
                site_url, key, "/apply-fix",
                {"change_id": change_id, "fix_type": change_type},
            )
            applied.append(
                {
                    "change_id": change_id,
                    "change_type": change_type,
                    "target": target,
                    "before": result.get("before_snapshot"),
                    "after": result.get("after_snapshot"),
                }
            )
        except FixError as exc:
            errors.append(f"{change_type} on {target}: {exc}")

    if not applied:
        raise FixError(
            "No WordPress fixes could be applied. " + " | ".join(errors)
        )

    change_ids = [str(a["change_id"]) for a in applied]
    types = sorted({a["change_type"] for a in applied})
    return FixHandlerResult(
        external_change_id=",".join(change_ids),
        issue_type="core_web_vitals",
        before_snapshot={
            "changes": [
                {k: a[k] for k in ("change_id", "change_type", "target", "before")}
                for a in applied
            ]
        },
        after_snapshot={
            "changes": [
                {k: a[k] for k in ("change_id", "change_type", "target", "after")}
                for a in applied
            ],
            "errors": errors,
        },
        detail=(
            f"Applied {len(applied)} WordPress fix(es) [{', '.join(types)}]"
            + (f"; {len(errors)} skipped" if errors else "")
            + "."
        ),
    )


async def _wordpress_revert(
    db: AsyncSession, project: Project, change: ChangeLog
) -> FixHandlerResult:
    """Revert every plugin change recorded for this ChangeLog row."""
    site_url, key = await _wp_credentials(db, project)
    change_ids = [
        piece.strip()
        for piece in (change.external_change_id or "").split(",")
        if piece.strip().isdigit()
    ]
    if not change_ids:
        raise FixError(
            "This change has no valid WordPress change id(s) to revert."
        )

    for change_id in change_ids:
        # 409 = already reverted on the WP side — treat as success (idempotent).
        await _wp_request(
            site_url, key, "/revert", {"change_id": int(change_id)},
            ok_statuses=(200, 409),
        )

    return FixHandlerResult(
        external_change_id=change.external_change_id,
        issue_type=change.issue_type,
        before_snapshot=change.after_snapshot,
        after_snapshot=change.before_snapshot,
        detail=f"Reverted {len(change_ids)} WordPress change(s) via the plugin.",
    )


# ---------------------------------------------------------------------------
# Shopify handler — STILL STUBBED (mock responses)
# ---------------------------------------------------------------------------


async def _shopify_fix_all(
    db: AsyncSession,
    project: Project,
    url: str,
    baseline: CoreWebVitals | None = None,
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

    # Baseline scan of this page: drives both the "before" score and the set
    # of fixes to apply (from its detected issues).
    baseline = await _latest_scan(db, project.id, url)
    cwv_before = baseline.performance_score if baseline else None

    result = await handler(db, project, url, baseline)

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
