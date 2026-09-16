"""Unit tests for the CWV fix orchestration service.

The DB and the Lighthouse re-scan are faked so the routing/flow logic can be
tested without Postgres or a browser: a lightweight async session stand-in and
a monkeypatched ``scan_and_store``.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.services import fix_service
from app.services.core_web_vitals_service import CoreWebVitalsError
from app.services.fix_service import FixError


class _Scalars:
    def __init__(self, items):
        self._items = items

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)


class FakeSession:
    """Minimal async-session stand-in for the orchestrator's DB calls."""

    def __init__(self, latest=None):
        self.latest = latest
        self.added = []

    async def execute(self, _stmt):
        return _Result([self.latest] if self.latest is not None else [])

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, _obj):
        pass


def _project(platform="wordpress"):
    return SimpleNamespace(
        id=uuid.uuid4(), platform=platform, domain="example.com"
    )


def _patch_scan(monkeypatch, *, score=88.0, fails=False):
    async def fake_scan(_db, _project_id, url):
        if fails:
            raise CoreWebVitalsError("lighthouse unavailable")
        return SimpleNamespace(performance_score=score, url=url)

    monkeypatch.setattr(
        fix_service.core_web_vitals_service, "scan_and_store", fake_scan
    )


def _patch_wp(monkeypatch):
    """Fake the WordPress plugin HTTP calls; return the recorded call list.

    /snapshot hands out incrementing change_ids so multi-fix plans get distinct
    ids; /apply-fix and /revert echo the id.
    """
    calls: list = []
    counter = {"n": 0}

    async def fake_creds(_db, _project):
        return ("https://wp.example", "APIKEY", "rest")

    async def fake_request(
        _site, _key, _transport, action, payload, ok_statuses=(200,)
    ):
        calls.append((action, payload))
        if action == "snapshot":
            counter["n"] += 1
            return {"change_id": counter["n"], "status": "snapshotted"}
        if action == "apply_fix":
            return {
                "change_id": payload["change_id"],
                "status": "applied",
                "before_snapshot": "BEFORE",
                "after_snapshot": "AFTER",
            }
        return {"change_id": payload["change_id"], "status": "reverted"}

    monkeypatch.setattr(fix_service, "_wp_credentials", fake_creds)
    monkeypatch.setattr(fix_service, "_wp_request", fake_request)
    return calls


async def test_fix_all_wordpress_calls_plugin_and_logs(monkeypatch) -> None:
    _patch_scan(monkeypatch, score=88.0)
    calls = _patch_wp(monkeypatch)
    # No report_json on the baseline → the plan falls back to a single lazy_load.
    latest = SimpleNamespace(performance_score=42.0, url="x", report_json=None)
    db = FakeSession(latest=latest)
    project = _project("wordpress")

    result = await fix_service.apply_fix_all(db, project, "https://example.com")

    assert result.rescan_status == "completed"
    change = result.change
    assert change.platform == "wordpress"
    # external_change_id is the plugin's change_id (not a mock uuid).
    assert change.external_change_id == "1"
    assert change.issue_type == "core_web_vitals"
    assert change.cwv_score_before == 42.0
    assert change.cwv_score_after == 88.0
    assert change.status == "applied"
    assert change.after_snapshot["changes"][0]["after"] == "AFTER"
    assert change in db.added
    # snapshot first, then apply_fix.
    assert [action for action, _ in calls] == ["snapshot", "apply_fix"]


def test_wordpress_fix_plan_from_issues() -> None:
    report = {
        "categories": {
            "performance": {
                "insights": [
                    {"id": "unsized-images"},
                    {
                        "id": "uses-optimized-images",
                        "resource_urls": ["https://x/a.jpg", "https://x/b.jpg"],
                    },
                    {
                        "id": "render-blocking-resources",
                        # app.css is confirmed unused (safe to defer); theme.css
                        # is render-blocking but NOT unused → critical, keep it.
                        "resource_urls": [
                            "https://x/app.css",
                            "https://x/theme.css",
                            "https://x/lib.js",
                        ],
                    },
                    {
                        "id": "unused-css-rules",
                        "resource_urls": ["https://x/app.css"],
                    },
                ],
                "diagnostics": [{"id": "font-display"}],
            }
        }
    }
    plan = fix_service._wordpress_fix_plan(report, "https://x/page")
    pairs = {(p["change_type"], p["target"]) for p in plan}
    assert ("image_dimensions", "https://x/page") in pairs
    assert ("font_display", "style.css") in pairs
    assert ("image_compression", "https://x/a.jpg") in pairs
    assert ("image_compression", "https://x/b.jpg") in pairs
    # Only the confirmed-unused stylesheet is deferred.
    assert ("defer_css", "https://x/app.css") in pairs
    # Critical (render-blocking but not unused) stylesheet is NOT deferred.
    assert ("defer_css", "https://x/theme.css") not in pairs
    # JS render-blocking resources are not deferrable via defer_css.
    assert ("defer_css", "https://x/lib.js") not in pairs
    # Image issues present → lazy-load the page too.
    assert ("lazy_load", "https://x/page") in pairs


def test_wordpress_fix_plan_excludes_lcp_image_from_lazy_load() -> None:
    report = {
        "lcp_element": '<img src="https://x/hero.png" class="hero">',
        "categories": {
            "performance": {
                "insights": [{"id": "unsized-images"}],
                "diagnostics": [],
            }
        },
    }
    plan = fix_service._wordpress_fix_plan(report, "https://x/page")
    lazy = next(p for p in plan if p["change_type"] == "lazy_load")
    # The LCP image URL is passed so the plugin can exclude it from lazy-load.
    assert lazy["data"]["lcp_url"] == "https://x/hero.png"


def test_wordpress_fix_plan_passes_flagged_images() -> None:
    """Scan-flagged image URLs ride along so the plugin can fail loud."""
    report = {
        "categories": {
            "performance": {
                "insights": [
                    {"id": "unsized-images", "resource_urls": ["https://x/a.jpg"]},
                    {
                        "id": "uses-optimized-images",
                        "resource_urls": ["https://x/b.jpg"],
                    },
                ],
                "diagnostics": [],
            }
        }
    }
    plan = fix_service._wordpress_fix_plan(report, "https://x/page")
    by_type = {p["change_type"]: p for p in plan}
    assert by_type["image_dimensions"]["data"]["flagged_urls"] == [
        "https://x/a.jpg",
        "https://x/b.jpg",
    ]
    assert by_type["lazy_load"]["data"]["flagged_urls"] == [
        "https://x/a.jpg",
        "https://x/b.jpg",
    ]


def test_wordpress_fix_plan_falls_back_to_lazy_load() -> None:
    assert fix_service._wordpress_fix_plan(None, "https://x/p") == [
        {"change_type": "lazy_load", "target": "https://x/p"}
    ]


async def test_fix_all_wordpress_applies_multiple_fixes(monkeypatch) -> None:
    _patch_scan(monkeypatch, score=90.0)
    calls = _patch_wp(monkeypatch)
    report = {
        "categories": {
            "performance": {
                "insights": [
                    {"id": "unsized-images"},
                    {
                        "id": "uses-optimized-images",
                        "resource_urls": ["https://x/a.jpg"],
                    },
                ],
                "diagnostics": [],
            }
        }
    }
    latest = SimpleNamespace(
        performance_score=50.0, url="https://x/page", report_json=report
    )
    result = await fix_service.apply_fix_all(
        FakeSession(latest=latest), _project("wordpress"), "https://x/page"
    )
    change = result.change
    ids = change.external_change_id.split(",")
    types = {c["change_type"] for c in change.after_snapshot["changes"]}
    # image_dimensions + image_compression + lazy_load, each a distinct id.
    assert len(ids) == 3
    assert types == {"image_dimensions", "image_compression", "lazy_load"}
    # Two plugin calls (snapshot + apply-fix) per applied fix.
    assert len(calls) == 6


async def test_wordpress_fix_requires_connection(monkeypatch) -> None:
    _patch_scan(monkeypatch)

    async def no_creds(_db, _project_id):
        return None

    monkeypatch.setattr(
        fix_service.connector_service, "get_credentials", no_creds
    )
    with pytest.raises(FixError, match="Connect the site"):
        await fix_service.apply_fix_all(
            FakeSession(), _project("wordpress"), "https://example.com"
        )


async def test_fix_all_shopify_uses_backup_theme_id(monkeypatch) -> None:
    _patch_scan(monkeypatch, score=75.0)
    db = FakeSession()
    result = await fix_service.apply_fix_all(
        db, _project("shopify"), "https://shop.example"
    )
    assert result.change.platform == "shopify"
    assert result.change.external_change_id.startswith("shopify-theme-backup-")
    # No prior scan → before score is null, after comes from the re-scan.
    assert result.change.cwv_score_before is None
    assert result.change.cwv_score_after == 75.0


async def test_fix_all_rejects_unsupported_platform(monkeypatch) -> None:
    _patch_scan(monkeypatch)
    with pytest.raises(FixError, match="custom"):
        await fix_service.apply_fix_all(FakeSession(), _project("custom"), "u")


async def test_fix_all_survives_rescan_failure(monkeypatch) -> None:
    _patch_scan(monkeypatch, fails=True)
    _patch_wp(monkeypatch)
    result = await fix_service.apply_fix_all(
        FakeSession(), _project("wordpress"), "https://example.com"
    )
    # The fix is still recorded even though the re-scan couldn't run.
    assert result.rescan_status == "failed"
    assert result.new_scan is None
    assert result.change.status == "applied"
    assert result.change.cwv_score_after is None
    assert "re-scan failed" in (result.detail or "")


async def test_revert_flips_status_and_rescans(monkeypatch) -> None:
    _patch_scan(monkeypatch, score=90.0)
    calls = _patch_wp(monkeypatch)
    from app.models.change_log import ChangeLog

    change = ChangeLog(
        project_id=uuid.uuid4(),
        platform="wordpress",
        issue_type="core_web_vitals",
        external_change_id="42",  # must parse to the plugin's change_id
        before_snapshot={"a": 1},
        after_snapshot={"b": 2},
        status="applied",
    )
    result = await fix_service.revert_fix(
        FakeSession(), _project("wordpress"), change
    )
    assert result.change.status == "reverted"
    assert result.change.cwv_score_after == 90.0
    assert result.rescan_status == "completed"
    assert ("revert", {"change_id": 42}) in calls


async def test_revert_rejects_already_reverted(monkeypatch) -> None:
    _patch_scan(monkeypatch)
    from app.models.change_log import ChangeLog

    change = ChangeLog(platform="wordpress", issue_type="x", status="reverted")
    with pytest.raises(FixError, match="already been reverted"):
        await fix_service.revert_fix(
            FakeSession(), _project("wordpress"), change
        )
