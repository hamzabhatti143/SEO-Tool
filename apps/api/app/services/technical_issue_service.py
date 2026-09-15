"""Technical-SEO issue detection engine (extends the audit crawler).

Runs as part of the Website Audit scan (``tasks.task_run_audit``). It crawls
the project's site (bounded) and detects, per project:

  * broken_internal_link  — internal 4xx/5xx links (+ fuzzy replacement)
  * broken_external_link   — external 4xx/5xx / DNS failures (suggest-only)
  * redirect_chain         — internal URLs with 2+ redirect hops
  * missing_canonical      — page has no <link rel="canonical">
  * incorrect_canonical    — canonical points elsewhere (same-domain fix, or
                             cross-domain flagged "review")
  * missing_sitemap        — no /sitemap.xml
  * sitemap_errors         — sitemap <loc> URLs that 404
  * duplicate_content      — pages sharing a near-identical title+meta+body hash
  * orphan_pages           — crawled pages with zero inbound internal links
  * mixed_content          — http:// resources on an https page (auto-fixable
                             when an https:// version is reachable)
  * missing_alt_text       — <img> with missing/empty alt

Each finding is classified with ``fix_confidence`` (auto | suggest | manual)
and stored in ``technical_seo_issues`` (previous rows replaced per scan). The
pure helpers (hashing, slug similarity, canonical logic) are network-free and
unit-tested; the crawl is bounded by ``TECH_ISSUE_*`` settings.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.technical_seo import TechnicalSEOIssue

_USER_AGENT = "RankPilotBot/0.1 (+https://rankpilot.ai/bot)"
_ASSET_RE = re.compile(
    r"\.(?:png|jpe?g|gif|svg|webp|ico|css|js|pdf|zip|mp4|mp3|woff2?|ttf)(?:\?|$)",
    re.IGNORECASE,
)

# fix_confidence values
AUTO = "auto"
SUGGEST = "suggest"
MANUAL = "manual"


# ---------------------------------------------------------------------------
# Pure helpers (network-free, unit-tested)
# ---------------------------------------------------------------------------
def normalize_url(url: str) -> str:
    """scheme://host/path with a trailing slash stripped (root stays '/')."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return f"{p.scheme}://{p.netloc}{path}"


def _slug(url: str) -> str:
    return urlparse(url).path.rstrip("/").lower()


def slug_similarity(a: str, b: str) -> float:
    """0–1 similarity of two URLs' path slugs (SequenceMatcher / Levenshtein-like)."""
    return SequenceMatcher(None, _slug(a), _slug(b)).ratio()


def best_replacement(
    broken_url: str, known_urls: list[str], threshold: float
) -> tuple[str, float] | None:
    """Closest known URL to ``broken_url`` by slug similarity, if >= threshold."""
    best: str | None = None
    best_score = 0.0
    for candidate in known_urls:
        if normalize_url(candidate) == normalize_url(broken_url):
            continue
        score = slug_similarity(broken_url, candidate)
        if score > best_score:
            best_score, best = score, candidate
    if best is not None and best_score >= threshold:
        return best, round(best_score, 3)
    return None


def content_signature(title: str | None, meta: str | None, body: str | None) -> str:
    """Whitespace/case-normalized hash of title + meta + main text."""
    text = " ".join(
        f"{title or ''} {meta or ''} {(body or '')[:2000]}".lower().split()
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_finding(
    page_url: str, canonical_href: str | None
) -> tuple[str, dict[str, Any], str] | None:
    """Return (issue_type, details, fix_confidence) for a canonical problem, else None."""
    if not canonical_href or not canonical_href.strip():
        return (
            "missing_canonical",
            {"reason": "No <link rel=\"canonical\"> on the page."},
            AUTO,  # safe to add a self-referential canonical
        )
    absolute = urljoin(page_url, canonical_href.strip())
    if normalize_url(absolute) == normalize_url(page_url):
        return None  # self-canonical — correct
    same_host = urlparse(absolute).netloc == urlparse(page_url).netloc
    if not same_host:
        # Cross-domain canonical can be intentional — flag for review, leave alone.
        return (
            "incorrect_canonical",
            {
                "canonical": absolute,
                "reason": "cross_domain_review",
                "note": "Canonical points to another domain — review; not auto-fixed.",
            },
            MANUAL,
        )
    return (
        "incorrect_canonical",
        {
            "canonical": absolute,
            "reason": "points_elsewhere",
            "note": "Canonical points to a different same-site URL.",
        },
        SUGGEST,
    )


def group_duplicates(pages: list["_Page"]) -> list[list[str]]:
    """Group crawled pages that share a content signature (near-identical)."""
    buckets: dict[str, list[str]] = {}
    for pg in pages:
        if not pg.html_ok:
            continue
        buckets.setdefault(pg.signature, []).append(pg.final_url)
    return [sorted(urls) for urls in buckets.values() if len(urls) > 1]


# ---------------------------------------------------------------------------
# Crawl model
# ---------------------------------------------------------------------------
@dataclass
class _Page:
    url: str
    final_url: str
    status: int
    html_ok: bool = False
    hops: list[dict[str, Any]] = field(default_factory=list)  # redirect chain
    canonical: str | None = None
    title: str | None = None
    meta: str | None = None
    signature: str = ""
    missing_alt: list[str] = field(default_factory=list)
    img_total: int = 0
    internal_links: set[str] = field(default_factory=set)
    external_links: set[str] = field(default_factory=set)
    http_resources: list[dict[str, str]] = field(default_factory=list)


def _parse_page(requested: str, resp: httpx.Response) -> _Page:
    final = str(resp.url)
    hops = [
        {"url": str(h.url), "status": h.status_code} for h in resp.history
    ]
    hops.append({"url": final, "status": resp.status_code})
    page = _Page(
        url=normalize_url(requested),
        final_url=final,
        status=resp.status_code,
        hops=hops,
    )
    if "text/html" not in resp.headers.get("content-type", ""):
        return page
    page.html_ok = True
    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("title")
    page.title = title_tag.get_text(strip=True) if title_tag else None
    md = soup.find("meta", attrs={"name": "description"})
    page.meta = (md.get("content") if md else None) or None
    canon = soup.find("link", attrs={"rel": lambda v: v and "canonical" in v})
    page.canonical = canon.get("href") if canon else None
    page.signature = content_signature(
        page.title, page.meta, soup.get_text(" ", strip=True)
    )

    imgs = soup.find_all("img")
    page.img_total = len(imgs)
    for img in imgs:
        if not (img.get("alt") or "").strip():
            src = (img.get("src") or "").strip()
            if src:
                page.missing_alt.append(urljoin(final, src))

    base_host = urlparse(final).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(final, href)
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        if _ASSET_RE.search(absolute):
            continue
        if urlparse(absolute).netloc == base_host:
            page.internal_links.add(normalize_url(absolute))
        else:
            page.external_links.add(absolute.split("#")[0])

    # Mixed content: http:// resources referenced from an https page.
    if urlparse(final).scheme == "https":
        for tag, attr in (
            ("img", "src"),
            ("script", "src"),
            ("link", "href"),
            ("iframe", "src"),
        ):
            for node in soup.find_all(tag):
                val = (node.get(attr) or "").strip()
                if val.startswith("http://"):
                    page.http_resources.append({"url": val, "type": tag})
    return page


# ---------------------------------------------------------------------------
# Network phases
# ---------------------------------------------------------------------------
async def _crawl(
    client: httpx.AsyncClient, start: str, base_host: str
) -> list[_Page]:
    max_pages = settings.TECH_ISSUE_MAX_PAGES
    queue: list[str] = [start]
    queued: set[str] = {start}
    pages: list[_Page] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        try:
            resp = await client.get(url)
        except httpx.HTTPError:
            continue
        page = _parse_page(url, resp)
        pages.append(page)
        for link in page.internal_links:
            if (
                link not in queued
                and len(queued) < max_pages * 3
                and urlparse(link).netloc == base_host
            ):
                queued.add(link)
                queue.append(link)
    return pages


async def _check_links(
    client: httpx.AsyncClient, urls: list[str]
) -> dict[str, dict[str, Any]]:
    """HEAD/GET each url; return {url: {status, error}}. Bounded + concurrent."""
    urls = urls[: settings.TECH_ISSUE_MAX_LINKS]
    sem = asyncio.Semaphore(settings.TECH_ISSUE_CONCURRENCY)

    async def one(u: str) -> tuple[str, dict[str, Any]]:
        async with sem:
            try:
                r = await client.head(u)
                if r.status_code >= 400:
                    r = await client.get(u, headers={"Range": "bytes=0-0"})
                return u, {"status": r.status_code, "error": None}
            except httpx.HTTPError as exc:
                return u, {"status": None, "error": type(exc).__name__}

    results = await asyncio.gather(*(one(u) for u in urls))
    return dict(results)


async def _check_sitemap(
    client: httpx.AsyncClient, root: str
) -> dict[str, Any]:
    """Fetch /sitemap.xml; report existence + any <loc> URLs that 404."""
    url = f"{root}/sitemap.xml"
    try:
        resp = await client.get(url)
    except httpx.HTTPError:
        return {"exists": False, "url": url, "broken": []}
    if resp.status_code != 200 or "<" not in resp.text:
        return {"exists": False, "url": url, "broken": []}

    locs: list[str] = []
    try:
        root_el = ET.fromstring(resp.text)
        for loc in root_el.iter():
            if loc.tag.endswith("loc") and loc.text:
                locs.append(loc.text.strip())
    except ET.ParseError:
        return {"exists": True, "url": url, "broken": [], "invalid": True}

    sample = locs[: settings.TECH_ISSUE_MAX_SITEMAP_CHECKS]
    statuses = await _check_links(client, sample)
    broken = [
        {"url": u, "status": s["status"]}
        for u, s in statuses.items()
        if s["status"] is None or s["status"] >= 400
    ]
    return {
        "exists": True,
        "url": url,
        "total_urls": len(locs),
        "checked": len(sample),
        "broken": broken,
    }


async def _check_https_upgrades(
    client: httpx.AsyncClient, http_urls: set[str]
) -> dict[str, bool]:
    """For each http:// resource, is the https:// version reachable?"""
    targets = list(http_urls)[: settings.TECH_ISSUE_MAX_LINKS]
    sem = asyncio.Semaphore(settings.TECH_ISSUE_CONCURRENCY)

    async def one(u: str) -> tuple[str, bool]:
        https = "https://" + u[len("http://") :]
        async with sem:
            try:
                r = await client.head(https)
                if r.status_code >= 400:
                    r = await client.get(https, headers={"Range": "bytes=0-0"})
                return u, r.status_code < 400
            except httpx.HTTPError:
                return u, False

    return dict(await asyncio.gather(*(one(u) for u in targets)))


# ---------------------------------------------------------------------------
# Build findings
# ---------------------------------------------------------------------------
def _build_issues(
    pages: list[_Page],
    link_status: dict[str, dict[str, Any]],
    https_reachable: dict[str, bool],
    sitemap: dict[str, Any],
    start: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    known_urls = [p.final_url for p in pages if p.html_ok and p.status < 400]
    threshold = settings.TECH_ISSUE_SLUG_MATCH_THRESHOLD

    def add(issue_type, page_url, details, fix_confidence):
        issues.append(
            {
                "issue_type": issue_type,
                "page_url": page_url[:2048],
                "details": details,
                "fix_confidence": fix_confidence,
            }
        )

    # Where each link was referenced (for context in broken-link findings).
    internal_refs: dict[str, list[str]] = {}
    external_refs: dict[str, list[str]] = {}
    for pg in pages:
        for link in pg.internal_links:
            internal_refs.setdefault(link, []).append(pg.final_url)
        for link in pg.external_links:
            external_refs.setdefault(link, []).append(pg.final_url)

    # 1 + 2) Broken links
    for link, refs in internal_refs.items():
        st = link_status.get(link)
        if st and st["status"] is not None and st["status"] >= 400:
            repl = best_replacement(link, known_urls, threshold)
            add(
                "broken_internal_link",
                link,
                {
                    "status_code": st["status"],
                    "referring_pages": refs[:10],
                    "suggested_replacement": repl[0] if repl else None,
                    "confidence": repl[1] if repl else 0.0,
                },
                SUGGEST,
            )
    for link, refs in external_refs.items():
        st = link_status.get(link)
        if st and (st["status"] is None or st["status"] >= 400):
            add(
                "broken_external_link",
                link,
                {
                    "status_code": st["status"],
                    "error": st["error"],
                    "referring_pages": refs[:10],
                    "suggest_only": True,
                },
                MANUAL,
            )

    # 3) Redirect chains (2+ hops) on crawled internal URLs
    for pg in pages:
        redirects = [h for h in pg.hops if 300 <= h["status"] < 400]
        if len(redirects) >= 2:
            add(
                "redirect_chain",
                pg.url,
                {
                    "hops": len(redirects),
                    "chain": pg.hops,
                    "final_url": pg.final_url,
                },
                SUGGEST,
            )

    # 4) Canonical + 9) alt text + 8) mixed content, per crawled page
    for pg in pages:
        if not pg.html_ok:
            continue
        canon = canonical_finding(pg.final_url, pg.canonical)
        if canon:
            add(canon[0], pg.final_url, canon[1], canon[2])

        if pg.missing_alt:
            add(
                "missing_alt_text",
                pg.final_url,
                {
                    "images_total": pg.img_total,
                    "missing_count": len(pg.missing_alt),
                    "images": pg.missing_alt[:20],
                },
                SUGGEST,
            )

        if pg.http_resources:
            resources = []
            all_upgradable = True
            for res in pg.http_resources:
                reachable = https_reachable.get(res["url"], False)
                all_upgradable = all_upgradable and reachable
                resources.append({**res, "https_reachable": reachable})
            add(
                "mixed_content",
                pg.final_url,
                {"resources": resources},
                AUTO if all_upgradable else MANUAL,
            )

    # 5) Sitemap
    if not sitemap.get("exists"):
        add(
            "missing_sitemap",
            sitemap.get("url", ""),
            {"reason": "No /sitemap.xml found (404 or non-XML)."},
            SUGGEST,
        )
    elif sitemap.get("invalid"):
        add(
            "sitemap_errors",
            sitemap.get("url", ""),
            {"reason": "sitemap.xml is not valid XML."},
            SUGGEST,
        )
    elif sitemap.get("broken"):
        add(
            "sitemap_errors",
            sitemap.get("url", ""),
            {
                "broken_urls": sitemap["broken"],
                "checked": sitemap.get("checked"),
                "total_urls": sitemap.get("total_urls"),
            },
            SUGGEST,
        )

    # 6) Duplicate content
    for group in group_duplicates(pages):
        add(
            "duplicate_content",
            group[0],
            {"urls": group, "count": len(group)},
            MANUAL,
        )

    # 7) Orphan pages (zero inbound internal links, excluding the start page)
    crawled = {p.final_url for p in pages if p.html_ok}
    crawled_norm = {normalize_url(u) for u in crawled}
    inbound: dict[str, int] = {normalize_url(u): 0 for u in crawled}
    for pg in pages:
        for link in pg.internal_links:
            if link in crawled_norm and link != normalize_url(pg.final_url):
                inbound[link] = inbound.get(link, 0) + 1
    start_norm = normalize_url(start)
    for pg in pages:
        if not pg.html_ok:
            continue
        nu = normalize_url(pg.final_url)
        if nu != start_norm and inbound.get(nu, 0) == 0:
            add("orphan_pages", pg.final_url, {"inbound_links": 0}, SUGGEST)

    return issues


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
async def detect_and_store(
    db: AsyncSession, project_id: uuid.UUID, page_url: str
) -> int:
    """Crawl + detect issues for the project; replace prior rows. Returns count."""
    if "://" not in page_url:
        page_url = f"https://{page_url}"
    p = urlparse(page_url)
    root = f"{p.scheme}://{p.netloc}"
    start = normalize_url(root)
    base_host = p.netloc

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=settings.AUDIT_REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        pages = await _crawl(client, start, base_host)

        internal_links = {ln for pg in pages for ln in pg.internal_links}
        external_links = {ln for pg in pages for ln in pg.external_links}
        # Check internal first (they can be auto-fixed), then external.
        link_status = await _check_links(
            client, list(internal_links) + list(external_links)
        )

        http_res = {r["url"] for pg in pages for r in pg.http_resources}
        https_reachable = (
            await _check_https_upgrades(client, http_res) if http_res else {}
        )

        sitemap = await _check_sitemap(client, root)

    issues = _build_issues(pages, link_status, https_reachable, sitemap, start)

    # Preserve issues the user has already resolved ("fixed") or chosen to
    # ignore across re-scans — only the transient open/reverted rows are
    # replaced. Without this, a re-scan would wipe fixed issues and re-add them
    # as "open", making resolved problems look unfixed every time.
    kept = (
        (
            await db.execute(
                select(
                    TechnicalSEOIssue.issue_type, TechnicalSEOIssue.page_url
                ).where(
                    TechnicalSEOIssue.project_id == project_id,
                    TechnicalSEOIssue.status.in_(("fixed", "ignored")),
                )
            )
        )
        .all()
    )
    kept_keys = {(issue_type, page_url) for issue_type, page_url in kept}

    await db.execute(
        delete(TechnicalSEOIssue).where(
            TechnicalSEOIssue.project_id == project_id,
            TechnicalSEOIssue.status.not_in(("fixed", "ignored")),
        )
    )
    added = 0
    for it in issues:
        # Don't re-open something already fixed/ignored (matched by type + page).
        if (it["issue_type"], it["page_url"]) in kept_keys:
            continue
        db.add(
            TechnicalSEOIssue(
                project_id=project_id,
                issue_type=it["issue_type"],
                page_url=it["page_url"],
                details=it["details"],
                fix_confidence=it["fix_confidence"],
                status="open",
            )
        )
        added += 1
    await db.commit()
    return added
