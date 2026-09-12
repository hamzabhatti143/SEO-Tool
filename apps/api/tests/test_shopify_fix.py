"""Unit tests for the Shopify technical-SEO fix handler (pure logic + guards)."""

import pytest

from app.services import shopify_fix_service as s
from app.services.fix_service import FixError


def test_replace_href_swaps_both_quote_styles() -> None:
    html = "<a href=\"http://old/x\">a</a> <a href='http://old/x'>b</a>"
    out = s.replace_href(html, "http://old/x", "https://new/x")
    assert 'href="https://new/x"' in out
    assert "href='https://new/x'" in out
    assert "old" not in out


def test_upgrade_http_only_listed_resources() -> None:
    html = "src=http://a/i.png and src=http://b/j.png"
    out = s.upgrade_http(html, ["http://a/i.png"])
    assert "https://a/i.png" in out
    assert "http://b/j.png" in out  # not in the list → untouched


def test_redirect_path_normalization() -> None:
    assert s.redirect_path("https://shop.com/old-page/") == "/old-page"
    assert s.redirect_path("old-page") == "/old-page"
    assert s.redirect_path("https://shop.com") == "/"
    assert s.redirect_path("/a/b/") == "/a/b"


def test_canonical_inject_before_head_and_round_trips() -> None:
    layout = "<html><head><title>t</title></head><body>x</body></html>"
    injected = s.inject_canonical(layout, "old-page", "/old-page", "https://s/c")
    assert 'rel="canonical"' in injected
    # Injected before </head>.
    assert injected.lower().index("rankpilot canonical") < injected.lower().index("</head>")
    # Removing the managed block restores the original exactly.
    assert s.remove_canonical(injected, "old-page") == layout


def test_canonical_reinject_is_idempotent() -> None:
    layout = "<head></head>"
    once = s.inject_canonical(layout, "k", "/k", "https://s/1")
    twice = s.inject_canonical(once, "k", "/k", "https://s/2")
    # Still a single managed block (begin + end markers only).
    assert twice.count("RankPilot canonical: k") == 2
    assert "https://s/2" in twice and "https://s/1" not in twice


async def test_missing_sitemap_is_not_applicable_without_network() -> None:
    # missing_sitemap short-circuits before touching credentials/network.
    result = await s.apply_technical_fix(None, None, "missing_sitemap", "/x", {})
    assert result.external_change_id is None
    assert result.before_snapshot == {"not_applicable": True}
    assert "Not applicable" in (result.detail or "")


async def test_unsupported_fix_type_raises() -> None:
    with pytest.raises(FixError):
        await s.apply_technical_fix(None, None, "orphan_pages", "/x", {})
