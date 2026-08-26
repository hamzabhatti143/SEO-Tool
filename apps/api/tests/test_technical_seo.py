"""Unit tests for the technical-SEO analysis (schema / robots / llms.txt)."""

from app.services.technical_seo_service import (
    analyze_llms,
    analyze_robots,
    analyze_schema,
    robots_issues,
)

# --- Structured data --------------------------------------------------------


def test_json_ld_valid_and_invalid() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization",
     "name":"Acme","url":"https://acme.test","logo":"l.png"}
    </script>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","image":"p.png"}
    </script>
    """
    results = analyze_schema(html)
    by_type = {r["schema_type"]: r for r in results}
    assert by_type["Organization"]["is_valid"] is True
    assert by_type["Organization"]["fmt"] == "json-ld"
    # Product requires "name" → missing.
    assert by_type["Product"]["is_valid"] is False
    assert by_type["Product"]["missing_properties"] == ["name"]


def test_json_ld_graph_and_type_list() -> None:
    html = """
    <script type="application/ld+json">
    {"@graph":[
      {"@type":["WebPage","Article"],"headline":"Hi"},
      {"@type":"BreadcrumbList"}
    ]}
    </script>
    """
    results = analyze_schema(html)
    types = {r["schema_type"] for r in results}
    assert "WebPage" in types  # first type of the list is used
    breadcrumb = next(r for r in results if r["schema_type"] == "BreadcrumbList")
    assert breadcrumb["missing_properties"] == ["itemListElement"]


def test_invalid_json_ld_is_flagged() -> None:
    results = analyze_schema(
        '<script type="application/ld+json">{ not json }</script>'
    )
    assert results[0]["is_valid"] is False
    assert "invalid JSON" in results[0]["missing_properties"][0]


def test_microdata_detection() -> None:
    html = """
    <div itemscope itemtype="https://schema.org/LocalBusiness">
      <span itemprop="name">Acme</span>
    </div>
    """
    results = analyze_schema(html)
    biz = next(r for r in results if r["schema_type"] == "LocalBusiness")
    assert biz["fmt"] == "microdata"
    # address required but missing.
    assert biz["missing_properties"] == ["address"]


def test_no_schema_found() -> None:
    assert analyze_schema("<html><body>nothing</body></html>") == []


# --- robots.txt -------------------------------------------------------------


def test_robots_parse_and_issues() -> None:
    content = (
        "User-agent: *\n"
        "Disallow: /wp-admin/\n"
        "Disallow: /assets/\n"
        "# a comment\n"
        "Sitemap: https://x.test/sitemap.xml\n"
    )
    parsed = analyze_robots(content)
    assert parsed["user_agents"][0]["user_agent"] == "*"
    assert "/wp-admin/" in parsed["user_agents"][0]["disallow"]
    assert parsed["sitemaps"] == ["https://x.test/sitemap.xml"]
    issues = {i["code"] for i in robots_issues(parsed, exists=True)}
    assert "blocks_assets" in issues  # /assets/ blocked
    assert "no_sitemap" not in issues  # sitemap present


def test_robots_blocks_whole_site() -> None:
    parsed = analyze_robots("User-agent: *\nDisallow: /\n")
    issues = robots_issues(parsed, exists=True)
    codes = {i["code"] for i in issues}
    assert "blocks_site" in codes
    assert "no_sitemap" in codes
    blocks = next(i for i in issues if i["code"] == "blocks_site")
    assert blocks["severity"] == "critical"


def test_robots_missing() -> None:
    issues = robots_issues({"user_agents": [], "sitemaps": []}, exists=False)
    assert [i["code"] for i in issues] == ["missing"]


# --- llms.txt ---------------------------------------------------------------


def test_llms_follows_spec() -> None:
    good = (
        "# Acme Docs\n\n"
        "> Everything about Acme.\n\n"
        "## Guides\n"
        "- [Start](https://acme.test/start)\n"
    )
    assert analyze_llms(good) is True


def test_llms_not_spec_compliant() -> None:
    # No H1 / no H2 / no links.
    assert analyze_llms("just some plain text\nmore text") is False
    # H1 but no H2/links.
    assert analyze_llms("# Title only") is False
