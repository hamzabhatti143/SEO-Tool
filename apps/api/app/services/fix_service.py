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

import re
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
from app.models.technical_seo import TechnicalSEOIssue
from app.services import (
    connector_service,
    core_web_vitals_service,
    media_reserve_service,
    wordpress_service,
)
from app.services.core_web_vitals_service import CoreWebVitalsError
from app.services.scan_stability import compare_ranges

# The auto/suggest technical-SEO fix types that route to a platform handler
# (manual-only types like broken_external_link/duplicate_content/orphan_pages
# never reach an apply-fix action).
_TECHNICAL_FIX_TYPES = frozenset(
    {
        "redirect_chain",
        "missing_canonical",
        "incorrect_canonical",
        "missing_sitemap",
        "broken_internal_link",
        "mixed_content",
        "missing_alt_text",
    }
)

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
    # Range-based verdict (replaces single-run before/after deltas): "improved"
    # | "worsened" | "inconclusive" — only conclusive when the post-fix value
    # falls outside the page's recent score/CLS range (see scan_stability.py).
    verdict: str | None = field(default=None)
    verdict_detail: str | None = field(default=None)


# ---------------------------------------------------------------------------
# WordPress handler — real calls to the RankPilot Connector plugin
# ---------------------------------------------------------------------------


async def _wp_credentials(
    db: AsyncSession, project: Project
) -> tuple[str, str, str]:
    """Return (site_url, api_key, transport) for the WordPress connection.

    ``transport`` is the channel that verified at connect time ("rest" or the
    admin-ajax "ajax" fallback); defaults to "rest" for connections saved
    before transport detection existed.
    """
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
    return cred.site_url.rstrip("/"), key, cred.wp_transport or "rest"


async def _wp_request(
    site_url: str,
    key: str,
    transport: str,
    action: str,
    payload: dict[str, Any],
    ok_statuses: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    """POST to a plugin action over the stored transport; return parsed JSON.

    ``action`` is canonical ("snapshot" | "apply_fix" | "revert"); the URL and
    auth (Bearer header vs rankpilot_key param) are built by wordpress_service
    so REST and admin-ajax callers never diverge.
    """
    url, headers = wordpress_service.build_wp_request(
        site_url, action, transport, key
    )
    try:
        async with httpx.AsyncClient(
            timeout=settings.WORDPRESS_CONNECT_TIMEOUT
        ) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise FixError(f"Could not reach the WordPress plugin: {exc}") from exc

    if resp.status_code not in ok_statuses:
        detail = _wp_error_detail(resp)
        raise FixError(f"WordPress plugin error on {action}: {detail}")
    return resp.json()


def _lcp_image_url(report: dict[str, Any] | None) -> str | None:
    """Extract the LCP element's image URL from a scan report, if it's an image.

    ``report['lcp_element']`` is the Lighthouse largest-contentful-paint-element
    snippet (e.g. ``<img ... src="...">``). Returns the src URL, or None when
    the LCP isn't an image (text/background) or no snippet is present.
    """
    snippet = (report or {}).get("lcp_element")
    if not isinstance(snippet, str):
        return None
    m = re.search(r"""src\s*=\s*["']([^"']+)["']""", snippet)
    return m.group(1) if m else None


def _wordpress_fix_plan(
    report: dict[str, Any] | None, page_url: str
) -> list[dict[str, Any]]:
    """Turn a scan's detected performance audits into plugin fix instructions.

    Each instruction is ``{"change_type": ..., "target": ...}`` (plus an
    optional ``data`` dict). Falls back to a single safe lazy_load when there's
    no scan or no mappable issue.
    """
    audits: dict[str, dict[str, Any]] = {}
    perf = ((report or {}).get("categories") or {}).get("performance") or {}
    for group in ("insights", "diagnostics"):
        for item in perf.get(group) or []:
            if isinstance(item, dict) and item.get("id"):
                audits[item["id"]] = item

    plan: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(change_type: str, target: str, data: dict | None = None) -> None:
        key = (change_type, target)
        if target and key not in seen:
            seen.add(key)
            instr: dict[str, Any] = {"change_type": change_type, "target": target}
            if data:
                instr["data"] = data
            plan.append(instr)

    # Images the scan flagged (unsized / unoptimized / poorly delivered). These
    # travel with the content fixes so the plugin can verify they're actually in
    # post content and FAIL LOUD (instead of silently succeeding) when they're
    # theme/Customizer-rendered — the common reason a fix "applies" yet the
    # issue reappears on re-scan.
    flagged_images: list[str] = []
    for audit_id in (
        "unsized-images",
        "uses-optimized-images",
        "modern-image-formats",
        "image-delivery-insight",
        "image-delivery",
        "prioritize-lcp-image",
    ):
        for src in audits.get(audit_id, {}).get("resource_urls") or []:
            if src not in flagged_images:
                flagged_images.append(src)
    flagged_images = flagged_images[:20]

    # Page-level content fixes.
    if "unsized-images" in audits:
        add(
            "image_dimensions",
            page_url,
            {"flagged_urls": flagged_images} if flagged_images else None,
        )
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

    # Render-blocking resources (Lighthouse reports these under either id).
    render_blocking: list[str] = []
    for audit_id in ("render-blocking-resources", "render-blocking-insight"):
        render_blocking += audits.get(audit_id, {}).get("resource_urls") or []

    # Stylesheets → defer, but ONLY ones Lighthouse also flags as largely
    # unused. Deferring a critical (above-the-fold) stylesheet delays first
    # paint and LOWERS the score, so anything not confirmed unused is left alone.
    unused_css = {
        href.split("?", 1)[0]
        for href in audits.get("unused-css-rules", {}).get("resource_urls") or []
    }
    for href in render_blocking:
        base = href.split("?", 1)[0]
        if base.lower().endswith(".css") and base in unused_css:
            add("defer_css", href)

    # Scripts → defer to unblock first paint (often the biggest CWV lever). Never
    # jQuery: inline scripts depend on it synchronously and deferring it breaks
    # themes (the plugin guards this too). Fully revertible.
    for href in render_blocking:
        base = href.split("?", 1)[0]
        if base.lower().endswith(".js") and "jquery" not in base.lower():
            add("defer_js", href)

    # Lazy-load images when the page has image issues — but never the LCP image
    # (the plugin also always skips the first image). Passing the LCP URL lets
    # the plugin exclude that exact image even if it isn't first in the content.
    if audits.keys() & _IMAGE_AUDITS:
        lcp_url = _lcp_image_url(report)
        lazy_data: dict[str, Any] = {}
        if lcp_url:
            lazy_data["lcp_url"] = lcp_url
        if flagged_images:
            lazy_data["flagged_urls"] = flagged_images
        add("lazy_load", page_url, lazy_data or None)

    if not plan:
        add(_WORDPRESS_FALLBACK_FIX, page_url)

    return plan[:_WORDPRESS_MAX_FIXES]


def _has_layout_shift(report: dict[str, Any] | None) -> bool:
    """True when the scan shows meaningful CLS (so media-reserve is worth it)."""
    if not report:
        return False
    cls = (report.get("metrics") or {}).get("cls")
    if isinstance(cls, int | float) and cls > 0.1:
        return True
    perf = (report.get("categories") or {}).get("performance") or {}
    ids = {
        item.get("id")
        for group in ("insights", "diagnostics")
        for item in (perf.get(group) or [])
        if isinstance(item, dict)
    }
    return bool(ids & {"layout-shifts", "cls-culprits-insight"})


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
    site_url, key, transport = await _wp_credentials(db, project)
    report = baseline.report_json if baseline is not None else None
    plan = _wordpress_fix_plan(report, url)

    # reserve_media_dimensions (CLS): when the page has layout shift, detect
    # rotating-media containers and reserve their size. Separate from
    # compression — this is the actual CLS lever for carousels/sliders/video.
    if _has_layout_shift(report):
        for reserve in await media_reserve_service.fetch_and_detect(url):
            plan.append(
                {
                    "change_type": "reserve_media_dimensions",
                    "target": reserve["selector"],
                    "data": reserve["data"],
                }
            )

    applied: list[dict[str, Any]] = []
    errors: list[str] = []
    for instr in plan:
        change_type = instr["change_type"]
        target = instr["target"]
        # data (e.g. lcp_url for lazy_load) is stored at snapshot time and used
        # by the plugin's apply step, so it must travel on the snapshot call.
        snapshot_payload: dict[str, Any] = {
            "change_type": change_type,
            "target": target,
        }
        if instr.get("data"):
            snapshot_payload["data"] = instr["data"]
        try:
            snap = await _wp_request(
                site_url, key, transport, "snapshot", snapshot_payload
            )
            change_id = snap.get("change_id")
            if change_id is None:
                raise FixError("snapshot did not return a change_id.")
            result = await _wp_request(
                site_url, key, transport, "apply_fix",
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
    site_url, key, transport = await _wp_credentials(db, project)
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
            site_url, key, transport, "revert", {"change_id": int(change_id)},
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
# Technical-SEO fix routing (same ChangeLog + revert pattern as CWV)
# ---------------------------------------------------------------------------


def _alt_for(image_url: str, page_url: str) -> str:
    """Derive alt text for an image (filename → words). AI can override later."""
    slug = image_url.rstrip("/").split("/")[-1].split("?")[0]
    slug = slug.rsplit(".", 1)[0]  # drop extension
    words = slug.replace("-", " ").replace("_", " ").strip()
    return words[:120] or "Image"


def _technical_plan(issue: TechnicalSEOIssue) -> tuple[str, str, dict[str, Any]]:
    """Map a detected issue to a handler's (fix_type, target, data)."""
    ft = issue.issue_type
    d = issue.details or {}
    if ft == "redirect_chain":
        chain = [h.get("url") for h in (d.get("chain") or []) if h.get("url")]
        return ft, issue.page_url, {"final_url": d.get("final_url"), "chain": chain}
    if ft in ("missing_canonical", "incorrect_canonical"):
        # The correct canonical is the page's own URL (self-referential).
        return ft, issue.page_url, {"canonical": issue.page_url}
    if ft == "missing_sitemap":
        return ft, "site", {}
    if ft == "broken_internal_link":
        refs = d.get("referring_pages") or []
        target = refs[0] if refs else issue.page_url
        return ft, target, {
            "broken_url": issue.page_url,
            "replacement_url": d.get("suggested_replacement"),
        }
    if ft == "mixed_content":
        resources = [
            r.get("url")
            for r in (d.get("resources") or [])
            if r.get("url") and r.get("https_reachable")
        ]
        return ft, issue.page_url, {"resources": resources}
    if ft == "missing_alt_text":
        images = d.get("images") or []
        target = images[0] if images else issue.page_url
        return ft, target, {"alt": _alt_for(str(target), issue.page_url)}
    raise FixError(f"'{ft}' has no automated fix.")


async def _wordpress_technical_apply(
    db: AsyncSession, project: Project, fix_type: str, target: str, data: dict
) -> FixHandlerResult:
    """Snapshot + apply-fix one technical fix via the RankPilot Connector plugin."""
    site_url, key, transport = await _wp_credentials(db, project)
    snap = await _wp_request(
        site_url, key, transport, "snapshot",
        {"change_type": fix_type, "target": target, "data": data},
    )
    change_id = snap.get("change_id")
    if change_id is None:
        raise FixError("snapshot did not return a change_id.")
    result = await _wp_request(
        site_url, key, transport, "apply_fix",
        {"change_id": change_id, "fix_type": fix_type},
    )
    return FixHandlerResult(
        external_change_id=str(change_id),
        issue_type=fix_type,
        before_snapshot={"before": result.get("before_snapshot")},
        after_snapshot={"after": result.get("after_snapshot")},
        detail=f"Applied WordPress {fix_type} fix.",
    )


async def apply_technical_fix(
    db: AsyncSession, project: Project, issue: TechnicalSEOIssue
) -> OrchestrationResult:
    """Apply one auto/suggest technical-SEO fix, routed by platform, and log it."""
    if issue.fix_confidence == "manual":
        raise FixError(
            "This issue has no automated fix — resolve it manually."
        )
    if issue.issue_type not in _TECHNICAL_FIX_TYPES:
        raise FixError(f"'{issue.issue_type}' is not an auto-fixable issue.")

    fix_type, target, data = _technical_plan(issue)

    if project.platform == "wordpress":
        result = await _wordpress_technical_apply(
            db, project, fix_type, target, data
        )
    elif project.platform == "shopify":
        from app.services import shopify_fix_service  # lazy: avoids import cycle

        result = await shopify_fix_service.apply_technical_fix(
            db, project, fix_type, target, data
        )
    else:
        raise FixError(
            f"Project platform '{project.platform}' cannot be auto-fixed. "
            "Connect a WordPress or Shopify site first."
        )

    change = ChangeLog(
        project_id=project.id,
        platform=project.platform,
        issue_type=fix_type,
        external_change_id=result.external_change_id,
        before_snapshot={
            **(result.before_snapshot or {}),
            "technical_issue_id": str(issue.id),
        },
        after_snapshot=result.after_snapshot,
        applied_at=datetime.now(timezone.utc),
        status="applied",
    )
    db.add(change)
    issue.status = "fixed"
    await db.commit()
    await db.refresh(change)

    return OrchestrationResult(
        change=change,
        new_scan=None,
        rescan_status="skipped",
        detail=result.detail,
    )


async def _technical_revert(
    db: AsyncSession, project: Project, change: ChangeLog
) -> FixHandlerResult:
    """Revert a technical-SEO change on the right platform."""
    if project.platform == "wordpress":
        # The plugin reverts by its own change id(s) — reuse the CWV path.
        return await _wordpress_revert(db, project, change)
    if project.platform == "shopify":
        from app.services import shopify_fix_service  # lazy: avoids import cycle

        return await shopify_fix_service.revert_technical_fix(db, project, change)
    raise FixError(
        f"Project platform '{project.platform}' cannot be reverted."
    )


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

    verdict, verdict_detail = await _fix_verdict(db, project.id, url, new_scan)
    return OrchestrationResult(
        change=change,
        new_scan=new_scan,
        rescan_status=rescan_status,
        detail=detail or result.detail,
        verdict=verdict,
        verdict_detail=verdict_detail,
    )


async def revert_fix(
    db: AsyncSession, project: Project, change: ChangeLog
) -> OrchestrationResult:
    """Revert a previously applied change, then re-scan and record the result."""
    if change.status == "reverted":
        raise FixError("This change has already been reverted.")

    # Technical-SEO changes route to the technical revert and skip the CWV
    # re-scan (there's no CWV score to refresh); reopen the linked issue.
    if change.issue_type in _TECHNICAL_FIX_TYPES:
        result = await _technical_revert(db, project, change)
        change.status = "reverted"
        issue_id = (change.before_snapshot or {}).get("technical_issue_id")
        if issue_id:
            issue = await db.get(TechnicalSEOIssue, uuid.UUID(str(issue_id)))
            if issue is not None:
                issue.status = "reverted"
        await db.commit()
        await db.refresh(change)
        return OrchestrationResult(
            change=change,
            new_scan=None,
            rescan_status="skipped",
            detail=result.detail,
        )

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

    verdict, verdict_detail = await _fix_verdict(db, project.id, url, new_scan)
    return OrchestrationResult(
        change=change,
        new_scan=new_scan,
        rescan_status=rescan_status,
        detail=detail or result.detail,
        verdict=verdict,
        verdict_detail=verdict_detail,
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


async def _fix_verdict(
    db: AsyncSession, project_id: uuid.UUID, url: str, new_scan: CoreWebVitals | None
) -> tuple[str | None, str | None]:
    """Range-based verdict comparing the post-fix scan to the page's recent
    range — replaces misleading single-run deltas. Returns (verdict, detail).

    On a high-variance page the post-fix number usually lands inside the recent
    range, so the honest verdict is "inconclusive" rather than a fake
    improved/worsened. Never raises — verdict is advisory.
    """
    if new_scan is None:
        return None, None
    try:
        rows = (
            await db.execute(
                select(CoreWebVitals.performance_score, CoreWebVitals.cls)
                .where(
                    CoreWebVitals.project_id == project_id,
                    CoreWebVitals.url == url,
                    CoreWebVitals.id != new_scan.id,
                )
                .order_by(CoreWebVitals.scanned_at.desc())
                .limit(settings.STABILITY_HISTORY)
            )
        ).all()
    except Exception:  # noqa: BLE001 - verdict is advisory, never fatal
        return None, None
    before_scores = [r[0] for r in rows]
    before_cls = [r[1] for r in rows]
    score_v = compare_ranges(before_scores, [new_scan.performance_score])
    cls_v = compare_ranges(
        before_cls, [new_scan.cls], lower_is_better=True
    )

    if score_v.verdict == "inconclusive" and cls_v.verdict == "inconclusive":
        return (
            "inconclusive",
            "No conclusive change — the post-fix score/CLS are within this "
            "page's normal variance. Judge over several scans.",
        )
    parts = []
    if score_v.verdict != "inconclusive":
        parts.append(f"score {score_v.verdict} ({score_v.detail})")
    if cls_v.verdict != "inconclusive":
        parts.append(f"CLS {cls_v.verdict} ({cls_v.detail})")
    overall = (
        "worsened"
        if "worsened" in (score_v.verdict, cls_v.verdict)
        else "improved"
    )
    return overall, "; ".join(parts)


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
