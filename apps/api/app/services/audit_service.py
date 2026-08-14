"""Website Audit service.

Crawls a single URL with httpx + BeautifulSoup and produces a structured
SEO report: title/meta tags, H1–H6 structure, image alt-text coverage,
broken internal links, and page-load basics. No AI is used here — this is
deterministic HTML analysis. Issues are categorized Critical/Warning/Info
and rolled up into a 0–100 score.
"""

from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.schemas.audit import (
    AuditIssue,
    AuditResults,
    BrokenLink,
    HeadingReport,
    ImageReport,
    LinkReport,
    MetaTagReport,
    PageSpeedReport,
)

_USER_AGENT = "RankPilotBot/0.1 (+https://rankpilot.ai/bot)"


async def run_audit(url: str) -> tuple[AuditResults, float]:
    """Crawl ``url`` and return the audit results and an overall score."""
    if not urlparse(url).scheme:
        url = f"https://{url}"

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=settings.AUDIT_REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        start = time.perf_counter()
        response = await client.get(url)
        response_time_ms = (time.perf_counter() - start) * 1000

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        meta = _analyze_meta(soup)
        headings = _analyze_headings(soup)
        images = _analyze_images(soup)
        page_speed = _analyze_page_speed(response, html, response_time_ms)
        links = await _analyze_links(client, str(response.url), soup)

    issues = _derive_issues(meta, headings, images, page_speed, links)
    score = _score(issues)
    results = AuditResults(
        meta=meta,
        headings=headings,
        images=images,
        links=links,
        page_speed=page_speed,
        issues=issues,
    )
    return results, score


def _analyze_meta(soup: BeautifulSoup) -> MetaTagReport:
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content") if desc_tag else None

    robots_tag = soup.find("meta", attrs={"name": "robots"})

    return MetaTagReport(
        title=title,
        title_length=len(title) if title else 0,
        meta_description=description,
        meta_description_length=len(description) if description else 0,
        has_canonical=soup.find("link", attrs={"rel": "canonical"}) is not None,
        has_viewport=soup.find("meta", attrs={"name": "viewport"}) is not None,
        has_open_graph=soup.find("meta", attrs={"property": "og:title"})
        is not None,
        robots=robots_tag.get("content") if robots_tag else None,
    )


def _analyze_headings(soup: BeautifulSoup) -> HeadingReport:
    counts = {f"h{level}": len(soup.find_all(f"h{level}")) for level in range(1, 7)}
    h1s = soup.find_all("h1")
    return HeadingReport(
        h1_count=counts["h1"],
        h2_count=counts["h2"],
        h3_count=counts["h3"],
        h4_count=counts["h4"],
        h5_count=counts["h5"],
        h6_count=counts["h6"],
        h1_texts=[h.get_text(strip=True) for h in h1s][:10],
    )


def _analyze_images(soup: BeautifulSoup) -> ImageReport:
    images = soup.find_all("img")
    missing = [
        img for img in images if not (img.get("alt") or "").strip()
    ]
    samples = [img.get("src", "") or "(no src)" for img in missing][:10]
    return ImageReport(
        total=len(images),
        missing_alt=len(missing),
        missing_alt_samples=samples,
    )


def _analyze_page_speed(
    response: httpx.Response, html: str, response_time_ms: float
) -> PageSpeedReport:
    soup = BeautifulSoup(html, "html.parser")
    # Rough proxy for number of requests the page will trigger.
    request_count = (
        len(soup.find_all("img"))
        + len(soup.find_all("script"))
        + len(soup.find_all("link", attrs={"rel": "stylesheet"}))
    )
    return PageSpeedReport(
        response_time_ms=round(response_time_ms, 1),
        page_size_kb=round(len(html.encode("utf-8")) / 1024, 1),
        request_count_estimate=request_count,
        status_code=response.status_code,
    )


async def _analyze_links(
    client: httpx.AsyncClient, base_url: str, soup: BeautifulSoup
) -> LinkReport:
    """Classify links as internal/external and check internal ones for breakage."""
    base_host = urlparse(base_url).netloc
    internal: list[str] = []
    external_count = 0
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)

        if urlparse(absolute).netloc == base_host:
            internal.append(absolute)
        else:
            external_count += 1

    to_check = internal[: settings.AUDIT_MAX_LINKS_CHECKED]
    broken: list[BrokenLink] = []
    for link in to_check:
        try:
            resp = await client.head(link)
            # Some servers reject HEAD; fall back to a ranged GET.
            if resp.status_code >= 400:
                resp = await client.get(link, headers={"Range": "bytes=0-0"})
            if resp.status_code >= 400:
                broken.append(
                    BrokenLink(
                        url=link,
                        status_code=resp.status_code,
                        reason=f"HTTP {resp.status_code}",
                    )
                )
        except httpx.HTTPError as exc:
            broken.append(
                BrokenLink(url=link, status_code=None, reason=str(exc))
            )

    return LinkReport(
        internal_count=len(internal),
        external_count=external_count,
        checked=len(to_check),
        broken=broken,
    )


def _derive_issues(
    meta: MetaTagReport,
    headings: HeadingReport,
    images: ImageReport,
    page_speed: PageSpeedReport,
    links: LinkReport,
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []

    # --- Title ---
    if not meta.title:
        issues.append(
            AuditIssue(
                code="missing_title",
                severity="critical",
                message="The page has no <title> tag.",
                recommendation="Add a unique, descriptive title of 50–60 characters.",
            )
        )
    elif not 30 <= meta.title_length <= 60:
        issues.append(
            AuditIssue(
                code="title_length",
                severity="warning",
                message=f"Title length is {meta.title_length} characters.",
                recommendation="Aim for a title between 50 and 60 characters.",
            )
        )

    # --- Meta description ---
    if not meta.meta_description:
        issues.append(
            AuditIssue(
                code="missing_meta_description",
                severity="warning",
                message="The page has no meta description.",
                recommendation="Add a compelling meta description of 140–160 characters.",
            )
        )
    elif not 120 <= meta.meta_description_length <= 160:
        issues.append(
            AuditIssue(
                code="meta_description_length",
                severity="info",
                message=(
                    f"Meta description is {meta.meta_description_length} characters."
                ),
                recommendation="Aim for a meta description between 140 and 160 characters.",
            )
        )

    # --- Headings ---
    if headings.h1_count == 0:
        issues.append(
            AuditIssue(
                code="missing_h1",
                severity="critical",
                message="The page has no <h1> heading.",
                recommendation="Add exactly one H1 that describes the page topic.",
            )
        )
    elif headings.h1_count > 1:
        issues.append(
            AuditIssue(
                code="multiple_h1",
                severity="warning",
                message=f"The page has {headings.h1_count} <h1> headings.",
                recommendation="Use a single H1 per page for a clear content hierarchy.",
            )
        )

    total_subheadings = (
        headings.h2_count
        + headings.h3_count
        + headings.h4_count
        + headings.h5_count
        + headings.h6_count
    )
    if headings.h1_count > 0 and total_subheadings == 0:
        issues.append(
            AuditIssue(
                code="no_subheadings",
                severity="info",
                message="No H2–H6 subheadings were found.",
                recommendation="Break content into sections with H2–H6 for readability and SEO.",
            )
        )

    # --- Images ---
    if images.missing_alt > 0:
        issues.append(
            AuditIssue(
                code="images_missing_alt",
                severity="warning",
                message=(
                    f"{images.missing_alt} of {images.total} images are missing "
                    "alt text."
                ),
                recommendation="Add descriptive alt attributes to all meaningful images.",
            )
        )

    # --- Mobile / indexing meta ---
    if not meta.has_viewport:
        issues.append(
            AuditIssue(
                code="missing_viewport",
                severity="warning",
                message="No responsive viewport meta tag found.",
                recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1">.',
            )
        )

    if not meta.has_canonical:
        issues.append(
            AuditIssue(
                code="missing_canonical",
                severity="info",
                message="No canonical link tag found.",
                recommendation="Add a canonical URL to prevent duplicate-content issues.",
            )
        )

    # --- Page load ---
    if page_speed.response_time_ms > 1000:
        issues.append(
            AuditIssue(
                code="slow_response",
                severity="warning",
                message=f"Server responded in {page_speed.response_time_ms:.0f} ms.",
                recommendation="Target a server response time under 600 ms (caching, CDN).",
            )
        )

    if page_speed.page_size_kb > 2048:
        issues.append(
            AuditIssue(
                code="large_page",
                severity="info",
                message=f"HTML payload is {page_speed.page_size_kb:.0f} KB.",
                recommendation="Reduce page weight by trimming markup and deferring assets.",
            )
        )

    # --- Broken internal links ---
    for link in links.broken:
        issues.append(
            AuditIssue(
                code="broken_internal_link",
                severity="critical",
                message=f"Broken internal link: {link.url} ({link.reason}).",
                recommendation="Fix or remove the link, or set up a redirect.",
            )
        )

    return issues


def _score(issues: list[AuditIssue]) -> float:
    """Compute a 0–100 SEO score by deducting per-issue penalties."""
    penalties = {"critical": 15, "warning": 7, "info": 2}
    score = 100.0
    for issue in issues:
        score -= penalties.get(issue.severity, 5)
    return round(max(score, 0.0), 1)
