"""Unit tests for technical-SEO fix routing (plan mapping + guards)."""

import types

import pytest

from app.services import fix_service as f
from app.services.fix_service import FixError


def _issue(**kw):
    return types.SimpleNamespace(**kw)


def test_plan_redirect_chain() -> None:
    issue = _issue(
        issue_type="redirect_chain",
        page_url="https://s/old",
        details={"final_url": "https://s/new", "chain": [{"url": "https://s/mid"}]},
    )
    ft, target, data = f._technical_plan(issue)
    assert ft == "redirect_chain"
    assert target == "https://s/old"
    assert data == {"final_url": "https://s/new", "chain": ["https://s/mid"]}


def test_plan_canonical_is_self() -> None:
    issue = _issue(issue_type="incorrect_canonical", page_url="https://s/p", details={})
    ft, target, data = f._technical_plan(issue)
    assert (ft, target, data) == ("incorrect_canonical", "https://s/p", {"canonical": "https://s/p"})


def test_plan_broken_link_targets_referring_page() -> None:
    issue = _issue(
        issue_type="broken_internal_link",
        page_url="https://s/broken",
        details={"referring_pages": ["https://s/page"], "suggested_replacement": "https://s/fixed"},
    )
    ft, target, data = f._technical_plan(issue)
    assert target == "https://s/page"
    assert data == {"broken_url": "https://s/broken", "replacement_url": "https://s/fixed"}


def test_plan_mixed_content_only_reachable() -> None:
    issue = _issue(
        issue_type="mixed_content",
        page_url="https://s/p",
        details={"resources": [
            {"url": "http://a/x.js", "https_reachable": True},
            {"url": "http://b/y.js", "https_reachable": False},
        ]},
    )
    _, _, data = f._technical_plan(issue)
    assert data == {"resources": ["http://a/x.js"]}


def test_plan_missing_sitemap() -> None:
    issue = _issue(issue_type="missing_sitemap", page_url="https://s/sitemap.xml", details={})
    assert f._technical_plan(issue) == ("missing_sitemap", "site", {})


def test_alt_from_filename() -> None:
    assert f._alt_for("https://s/img/my-cool_photo.jpg", "https://s/p") == "my cool photo"


async def test_apply_rejects_manual_confidence() -> None:
    issue = _issue(issue_type="duplicate_content", fix_confidence="manual")
    with pytest.raises(FixError):
        await f.apply_technical_fix(None, None, issue)


async def test_apply_rejects_non_fixable_type() -> None:
    issue = _issue(issue_type="broken_external_link", fix_confidence="suggest")
    with pytest.raises(FixError):
        await f.apply_technical_fix(None, None, issue)
