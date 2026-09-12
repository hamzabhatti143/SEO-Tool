"""Unit tests for the technical-SEO issue detection engine (pure helpers)."""

from app.services import technical_issue_service as t
from app.services.technical_issue_service import _Page


def test_slug_similarity_ranks_closer_slugs_higher() -> None:
    close = t.slug_similarity("https://a.com/products", "https://a.com/product")
    far = t.slug_similarity("https://a.com/products", "https://a.com/contact")
    assert close > far
    assert 0.0 <= far <= close <= 1.0


def test_best_replacement_returns_close_match_above_threshold() -> None:
    known = ["https://a.com/products", "https://a.com/about"]
    match = t.best_replacement("https://a.com/produtcs", known, 0.6)
    assert match is not None
    url, score = match
    assert url == "https://a.com/products"
    assert score >= 0.6


def test_best_replacement_none_below_threshold() -> None:
    known = ["https://a.com/totally-different-page"]
    assert t.best_replacement("https://a.com/xyz", known, 0.6) is None


def test_content_signature_ignores_case_and_whitespace() -> None:
    a = t.content_signature("Hello", "Desc", "Main   body\ntext")
    b = t.content_signature("hello", "desc", "main body text")
    c = t.content_signature("Hello", "Desc", "different body")
    assert a == b
    assert a != c


def test_canonical_missing_is_auto() -> None:
    issue = t.canonical_finding("https://a.com/p", None)
    assert issue is not None
    assert issue[0] == "missing_canonical"
    assert issue[2] == t.AUTO


def test_canonical_self_reference_is_ok() -> None:
    assert t.canonical_finding("https://a.com/p", "https://a.com/p/") is None
    assert t.canonical_finding("https://a.com/p", "/p") is None


def test_canonical_cross_domain_is_manual_review() -> None:
    issue = t.canonical_finding("https://a.com/p", "https://other.com/p")
    assert issue is not None
    assert issue[0] == "incorrect_canonical"
    assert issue[1]["reason"] == "cross_domain_review"
    assert issue[2] == t.MANUAL


def test_canonical_same_site_elsewhere_is_suggest() -> None:
    issue = t.canonical_finding("https://a.com/p", "https://a.com/other")
    assert issue is not None
    assert issue[0] == "incorrect_canonical"
    assert issue[2] == t.SUGGEST


def _page(url: str, sig: str) -> _Page:
    return _Page(url=url, final_url=url, status=200, html_ok=True, signature=sig)


def test_group_duplicates_groups_matching_signatures() -> None:
    pages = [
        _page("https://a.com/1", "sig-x"),
        _page("https://a.com/2", "sig-x"),
        _page("https://a.com/3", "sig-y"),
    ]
    groups = t.group_duplicates(pages)
    assert len(groups) == 1
    assert set(groups[0]) == {"https://a.com/1", "https://a.com/2"}
