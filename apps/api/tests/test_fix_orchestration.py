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
    """Fake the WordPress plugin HTTP calls; return the recorded call list."""
    calls: list = []

    async def fake_creds(_db, _project):
        return ("https://wp.example", "APIKEY")

    async def fake_request(_site, _key, path, payload):
        calls.append((path, payload))
        if path == "/snapshot":
            return {"change_id": 42, "status": "snapshotted"}
        if path == "/apply-fix":
            return {
                "change_id": 42,
                "status": "applied",
                "before_snapshot": "BEFORE",
                "after_snapshot": "AFTER",
            }
        return {"change_id": 42, "status": "reverted"}

    monkeypatch.setattr(fix_service, "_wp_credentials", fake_creds)
    monkeypatch.setattr(fix_service, "_wp_request", fake_request)
    return calls


async def test_fix_all_wordpress_calls_plugin_and_logs(monkeypatch) -> None:
    _patch_scan(monkeypatch, score=88.0)
    calls = _patch_wp(monkeypatch)
    db = FakeSession(latest=SimpleNamespace(performance_score=42.0, url="x"))
    project = _project("wordpress")

    result = await fix_service.apply_fix_all(db, project, "https://example.com")

    assert result.rescan_status == "completed"
    change = result.change
    assert change.platform == "wordpress"
    # external_change_id is the plugin's change_id (not a mock uuid).
    assert change.external_change_id == "42"
    assert change.issue_type == "core_web_vitals"
    assert change.cwv_score_before == 42.0
    assert change.cwv_score_after == 88.0
    assert change.status == "applied"
    assert change.after_snapshot["snapshot"] == "AFTER"
    assert change in db.added
    # /snapshot first, then /apply-fix.
    assert [path for path, _ in calls] == ["/snapshot", "/apply-fix"]


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
    assert ("/revert", {"change_id": 42}) in calls


async def test_revert_rejects_already_reverted(monkeypatch) -> None:
    _patch_scan(monkeypatch)
    from app.models.change_log import ChangeLog

    change = ChangeLog(platform="wordpress", issue_type="x", status="reverted")
    with pytest.raises(FixError, match="already been reverted"):
        await fix_service.revert_fix(
            FakeSession(), _project("wordpress"), change
        )
