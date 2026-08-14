"""Competitor Intelligence service.

Deterministic, robots/sitemap/canonical-aware crawl of a site (httpx +
BeautifulSoup), applied identically to BOTH the competitor and the user's own
site so the two are compared on equal footing. From the crawls we compute
page structure, internal-link hubs, and — deterministically — topic overlap
and keyword gaps (see ``competitor_compare``). The LLM is used only to narrate
strategy and estimate traffic/authority, and every figure's provenance
(measured-crawl vs AI-estimate vs provider) is recorded.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from agents import Runner
from bs4 import BeautifulSoup

from app.agents.competitor_agent import competitor_agent
from app.core.config import settings
from app.schemas.competitor import (
    Comparison,
    CompetitorAnalysis,
    CompetitorNarrative,
    CompetitorProfile,
    CompetitorReport,
    ContentGap,
    CrawledPage,
    CrawlStatus,
    HubPage,
    SiteStructure,
    UserProjectSummary,
)
from app.services import competitor_compare, seo_data_provider

# Present a mainstream browser UA so we aren't trivially 403'd by sites that
# block unknown bot user-agents (robots.txt is still respected via the "*"
# record below). ``_ROBOTS_AGENT`` is the token used for robots matching.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_ROBOTS_AGENT = "RankPilotBot"
_BROWSER_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_ASSET_RE = re.compile(
    r"\.(?:png|jpe?g|gif|svg|webp|ico|css|js|pdf|zip|mp4|mp3|woff2?|ttf)(?:\?|$)",
    re.IGNORECASE,
)
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _text(node) -> str | None:
    """Extract element text with a space separator so nested tags don't glue
    words together (e.g. '<h1>Welcome to<span>Oscar</span></h1>')."""
    if node is None:
        return None
    return _WS_RE.sub(" ", node.get_text(" ", strip=True)).strip() or None


def _ensure_scheme(url: str) -> str:
    return url if urlparse(url).scheme else f"https://{url}"


def _normalize(url: str) -> str:
    """Drop fragments and trailing slashes for de-duplication."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.netloc}{path}{query}"


def _same_host(url: str, host: str) -> bool:
    return urlparse(url).netloc == host


# --- Fetch primitive ----------------------------------------------------
@dataclass
class _Fetched:
    url: str
    status_code: int | None = None
    html: str | None = None
    error: str | None = None  # stable reason code, None on success
    detail: str = ""


async def _fetch(client: httpx.AsyncClient, url: str) -> _Fetched:
    try:
        resp = await client.get(url)
    except httpx.TimeoutException:
        return _Fetched(url, error="timeout", detail="Request timed out.")
    except httpx.ConnectError as exc:
        return _Fetched(
            url, error="connection_error", detail=f"Could not connect: {exc}"
        )
    except httpx.HTTPError as exc:
        return _Fetched(url, error="http_error", detail=str(exc))

    if resp.status_code >= 400:
        return _Fetched(
            str(resp.url),
            status_code=resp.status_code,
            error="http_error",
            detail=f"HTTP {resp.status_code}",
        )
    if "text/html" not in resp.headers.get("content-type", ""):
        return _Fetched(
            str(resp.url),
            status_code=resp.status_code,
            error="non_html",
            detail="Response was not HTML.",
        )
    return _Fetched(str(resp.url), status_code=resp.status_code, html=resp.text)


# --- robots.txt + sitemaps ---------------------------------------------
async def _load_robots(
    client: httpx.AsyncClient, base_url: str
) -> tuple[RobotFileParser | None, list[str]]:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = await client.get(robots_url)
    except httpx.HTTPError:
        return None, []
    if resp.status_code >= 400 or not resp.text.strip():
        return None, []
    rp = RobotFileParser()
    rp.parse(resp.text.splitlines())
    return rp, list(rp.site_maps() or [])


async def _load_sitemap_urls(
    client: httpx.AsyncClient, base_url: str, robots_sitemaps: list[str]
) -> set[str]:
    """Collect page URLs from sitemap(s), recursing sitemap-indexes."""
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    # Always probe the well-known sitemap locations in addition to whatever
    # robots.txt lists — some robots files point at a bad/empty URL (e.g. the
    # homepage), so relying on them alone misses the real sitemap.
    defaults = [
        f"{root}/sitemap.xml",
        f"{root}/sitemap_index.xml",
        f"{root}/sitemap-index.xml",
        f"{root}/wp-sitemap.xml",
        f"{root}/sitemap/",
    ]
    queue: list[str] = list(dict.fromkeys(list(robots_sitemaps) + defaults))
    seen: set[str] = set()
    urls: set[str] = set()

    while (
        queue
        and len(seen) < settings.COMPETITOR_MAX_SITEMAPS
        and len(urls) < settings.COMPETITOR_MAX_SITEMAP_URLS
    ):
        sitemap = queue.pop(0)
        if sitemap in seen:
            continue
        seen.add(sitemap)
        fetched = await _fetch(client, sitemap)
        text = fetched.html
        if text is None:
            # Sitemaps are often served as application/xml, not text/html;
            # re-fetch raw if the content-type guard rejected it.
            if fetched.error == "non_html":
                try:
                    text = (await client.get(sitemap)).text
                except httpx.HTTPError:
                    continue
            else:
                continue
        locs = [loc.strip() for loc in _LOC_RE.findall(text)]
        if "<sitemapindex" in text.lower():
            for loc in locs:
                if len(seen) + len(queue) < settings.COMPETITOR_MAX_SITEMAPS * 2:
                    queue.append(loc)
        else:
            for loc in locs:
                urls.add(_normalize(loc))
                if len(urls) >= settings.COMPETITOR_MAX_SITEMAP_URLS:
                    break
    return urls


# --- Page extraction ----------------------------------------------------
def _extract_page(
    fetched: _Fetched, base_host: str
) -> tuple[CrawledPage, list[str]]:
    soup = BeautifulSoup(fetched.html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    heading_count = sum(len(soup.find_all(f"h{i}")) for i in range(1, 7))

    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_description = (
        desc_tag.get("content", "").strip() if desc_tag else None
    ) or None

    canon_tag = soup.find("link", rel="canonical")
    canonical = None
    if canon_tag and canon_tag.get("href"):
        canonical = _normalize(urljoin(fetched.url, canon_tag["href"].strip()))

    robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    indexable = not (
        robots_tag and "noindex" in robots_tag.get("content", "").lower()
    )

    word_count = len(soup.get_text(" ", strip=True).split())

    internal_links: list[str] = []
    external = 0
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(fetched.url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https") or _ASSET_RE.search(absolute):
            continue
        if parsed.netloc == base_host:
            internal_links.append(_normalize(absolute))
        else:
            external += 1

    page = CrawledPage(
        url=_normalize(fetched.url),
        status_code=fetched.status_code,
        title=_text(title_tag),
        h1=_text(h1_tag),
        meta_description=meta_description,
        canonical=canonical,
        heading_count=heading_count,
        word_count=word_count,
        internal_link_count=len(internal_links),
        external_link_count=external,
        indexable=indexable,
    )
    return page, internal_links


# --- Crawl orchestration ------------------------------------------------
def _failed_profile(
    start: str, host: str, probe: _Fetched, sitemap_count: int | None
) -> CompetitorProfile:
    return CompetitorProfile(
        url=start,
        domain=host,
        crawl_status=CrawlStatus(
            ok=False, reason=probe.error or "empty", detail=probe.detail
        ),
        structure=SiteStructure(sitemap_url_count=sitemap_count),
    )


async def crawl_site(
    competitor_url: str, max_pages: int | None = None
) -> CompetitorProfile:
    """Crawl a site (robots + sitemap aware) and return its profile — no AI.

    Reused by the Content Gap Analysis module for each competitor.
    """
    competitor_url = _ensure_scheme(competitor_url)
    base_host = urlparse(competitor_url).netloc
    cap = max_pages or settings.COMPETITOR_MAX_PAGES

    async with httpx.AsyncClient(
        headers=_BROWSER_HEADERS,
        timeout=settings.AUDIT_REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        return await _crawl_site(client, competitor_url, base_host, cap)


async def _crawl_site(
    client: httpx.AsyncClient, start_url: str, base_host: str, max_pages: int
) -> CompetitorProfile:
    start = _normalize(start_url)
    rp, robots_sitemaps = await _load_robots(client, start_url)
    sitemap_urls = await _load_sitemap_urls(client, start_url, robots_sitemaps)
    sitemap_count = len(sitemap_urls) or None

    # Probe the start URL so a dead/blocked site fails loudly instead of
    # silently producing an empty (but "successful") report.
    probe = await _fetch(client, start)
    if probe.error:
        return _failed_profile(start, base_host, probe, sitemap_count)

    frontier: set[str] = {start} | {
        u for u in sitemap_urls if _same_host(u, base_host)
    }
    discovered: set[str] = set(frontier)
    requested: set[str] = set()
    pages: dict[str, CrawledPage] = {}
    inbound: Counter[str] = Counter()
    total_internal = 0
    disallowed = 0
    duplicates = 0
    discovery_cap = max(max_pages * 20, 200)

    while frontier and len(pages) < max_pages:
        remaining = max_pages - len(pages)
        # Deterministic: always take the lexicographically smallest URLs, so
        # the crawled set is stable across runs for an unchanged site.
        batch = sorted(frontier - requested)[
            : min(settings.COMPETITOR_MAX_CONCURRENCY, remaining)
        ]
        if not batch:
            break
        frontier -= set(batch)
        requested.update(batch)

        allowed: list[str] = []
        for url in batch:
            if (
                settings.COMPETITOR_RESPECT_ROBOTS
                and rp is not None
                and not rp.can_fetch(_ROBOTS_AGENT, url)
            ):
                disallowed += 1
                continue
            allowed.append(url)

        results = await asyncio.gather(*(_fetch(client, u) for u in allowed))
        for fetched in results:
            if fetched.error or fetched.html is None:
                continue
            page, links = _extract_page(fetched, base_host)
            key = page.canonical or page.url
            if key in pages:
                duplicates += 1
                continue
            pages[key] = page
            total_internal += page.internal_link_count
            for link in links:
                inbound[link] += 1
                if link not in discovered and len(discovered) < discovery_cap:
                    discovered.add(link)
                    if link not in requested:
                        frontier.add(link)

    ordered = [pages[k] for k in sorted(pages)]
    crawled = len(ordered)
    total_words = sum(p.word_count for p in ordered)
    structure = SiteStructure(
        pages_crawled=crawled,
        pages_discovered=len(discovered),
        sitemap_url_count=sitemap_count,
        total_internal_links=total_internal,
        avg_internal_links_per_page=(
            round(total_internal / crawled, 1) if crawled else 0.0
        ),
        avg_word_count=round(total_words / crawled) if crawled else 0.0,
        indexable_pages=sum(1 for p in ordered if p.indexable),
        duplicate_pages_collapsed=duplicates,
        disallowed_by_robots=disallowed,
        top_hub_pages=[
            HubPage(url=u, inbound_links=n) for u, n in inbound.most_common(5)
        ],
    )

    status = (
        CrawlStatus(ok=True, reason="ok")
        if crawled
        else CrawlStatus(
            ok=False,
            reason="empty",
            detail="No HTML pages could be crawled from this site.",
        )
    )
    return CompetitorProfile(
        url=start,
        domain=base_host,
        crawl_status=status,
        sample_titles=[p.title for p in ordered if p.title][:12],
        top_headings=[p.h1 for p in ordered if p.h1][:12],
        structure=structure,
        pages=ordered,
    )


# --- Analysis (crawl both sides + AI narrative) -------------------------
async def analyze(
    competitor_url: str, user_summary: UserProjectSummary
) -> CompetitorReport:
    # Crawl the user's own site and the competitor with identical methodology.
    user_site, competitor = await asyncio.gather(
        crawl_site(user_summary.domain),
        crawl_site(competitor_url),
    )
    comparison = competitor_compare.compare(user_site, competitor)
    analysis = await _build_analysis(
        competitor, user_site, user_summary, comparison
    )
    return CompetitorReport(
        competitor=competitor,
        user_site=user_site,
        user_project=user_summary,
        comparison=comparison,
        analysis=analysis,
    )


async def _build_analysis(
    competitor: CompetitorProfile,
    user_site: CompetitorProfile,
    user: UserProjectSummary,
    comparison: Comparison,
) -> CompetitorAnalysis:
    # Never analyze a site we could not crawl — report the reason instead.
    if not competitor.crawl_status.ok:
        return CompetitorAnalysis(
            content_strategy=(
                "The competitor site could not be crawled "
                f"({competitor.crawl_status.detail or competitor.crawl_status.reason}). "
                "No analysis was generated, to avoid guessing on incomplete data."
            ),
            estimated_traffic_band="n/a",
            estimated_authority=0,
        )

    narrative = await _narrate(competitor, user_site, comparison)

    # Prefer first-party provider metrics when configured; else AI estimates.
    provider = await seo_data_provider.get_domain_metrics(competitor.domain)
    if provider and provider.domain_authority is not None:
        authority = provider.domain_authority
        authority_source = "provider"
    else:
        authority = narrative.estimated_authority
        authority_source = "ai_estimate"
    if provider and provider.organic_traffic is not None:
        traffic_band = f"{provider.organic_traffic:,} / mo"
        traffic_source = "provider"
    else:
        traffic_band = narrative.estimated_traffic_band or "unknown"
        traffic_source = "ai_estimate"

    # Deterministic gaps drive content_gaps; the LLM supplies rationales.
    rationale_by_topic = {
        g.topic.lower(): g.rationale for g in narrative.content_gap_rationales
    }
    content_gaps = [
        ContentGap(
            topic=topic,
            rationale=rationale_by_topic.get(
                topic.lower(),
                "Covered by the competitor but not found on your site.",
            ),
        )
        for topic in comparison.keyword_gaps[:8]
    ]

    # Symmetric estimate for the user's own site (provider if configured).
    user_provider = await seo_data_provider.get_domain_metrics(user_site.domain)
    if user_provider and user_provider.domain_authority is not None:
        user_authority = user_provider.domain_authority
        user_authority_source = "provider"
    else:
        user_authority = narrative.user_estimated_authority
        user_authority_source = "ai_estimate"
    if user_provider and user_provider.organic_traffic is not None:
        user_traffic_band = f"{user_provider.organic_traffic:,} / mo"
        user_traffic_source = "provider"
    else:
        user_traffic_band = narrative.user_estimated_traffic_band or "unknown"
        user_traffic_source = "ai_estimate"

    return CompetitorAnalysis(
        content_strategy=narrative.content_strategy,
        topic_focus_areas=narrative.topic_focus_areas,
        estimated_traffic_band=traffic_band,
        traffic_source=traffic_source,
        estimated_authority=authority,
        authority_source=authority_source,
        user_estimated_traffic_band=user_traffic_band,
        user_traffic_source=user_traffic_source,
        user_estimated_authority=user_authority,
        user_authority_source=user_authority_source,
        keyword_gaps=comparison.keyword_gaps,
        content_gaps=content_gaps,
        shared_topics=comparison.shared_topics,
        recommendations=narrative.recommendations,
    )


async def _narrate(
    competitor: CompetitorProfile,
    user_site: CompetitorProfile,
    comparison: Comparison,
) -> CompetitorNarrative:
    cs = competitor.structure
    prompt = (
        "COMPETITOR SITE (measured crawl)\n"
        f"Domain: {competitor.domain}\n"
        f"Pages crawled: {cs.pages_crawled} | discovered: {cs.pages_discovered}"
        f" | sitemap URLs: {cs.sitemap_url_count if cs.sitemap_url_count is not None else 'unknown'}\n"
        f"Avg internal links/page: {cs.avg_internal_links_per_page}\n"
        "Sample page titles:\n- " + "\n- ".join(competitor.sample_titles or ["(none)"]) + "\n"
        "Top H1 headings:\n- " + "\n- ".join(competitor.top_headings or ["(none)"]) + "\n\n"
        "USER SITE (measured crawl, same method)\n"
        f"Domain: {user_site.domain}\n"
        f"Pages crawled: {user_site.structure.pages_crawled}\n"
        "Sample titles:\n- " + "\n- ".join(user_site.sample_titles or ["(none)"]) + "\n\n"
        "DETERMINISTIC COMPARISON (already computed — explain, do NOT change)\n"
        f"Shared topics: {', '.join(comparison.shared_topics) or '(none)'}\n"
        f"Keyword/content gaps (competitor-only): {', '.join(comparison.keyword_gaps) or '(none)'}\n\n"
        "Write the content strategy, topic focus areas, a short rationale for "
        "each gap topic above, an AI-ESTIMATED traffic band and 0–100 "
        "authority (clearly rough inferences), and prioritized recommendations."
    )
    result = await Runner.run(competitor_agent, prompt)
    return result.final_output  # type: ignore[return-value]
