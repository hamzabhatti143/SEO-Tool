"""Backlink Center service.

Two capabilities:
  1. Backlink profile — fetch basic backlink data for a domain from a
     free-tier provider (OpenLinkProfiler by default) and aggregate
     referring domains, anchor-text distribution, and follow/nofollow ratio.
  2. Broken Link Building — crawl a page and flag broken outbound links
     (opportunities to pitch replacement content).

Provider design: `fetch_backlinks` normalizes any provider's response into a
common `Backlink` shape, so a paid provider (Ahrefs/Semrush) can be added as
another branch later. Free-tier data is limited and clearly labeled as such.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.schemas.backlinks import (
    AnchorCount,
    BacklinkProfileResponse,
    BrokenLinkResponse,
    BrokenOutboundLink,
    SampleBacklink,
)

_USER_AGENT = "RankPilotBot/0.1 (+https://rankpilot.ai/bot)"


@dataclass
class Backlink:
    source_url: str
    source_domain: str
    anchor: str
    nofollow: bool


def _host(value: str) -> str:
    host = urlparse(value if "://" in value else f"//{value}").netloc or value
    return host.lower().removeprefix("www.")


# --- Provider fetch -----------------------------------------------------
async def _fetch_backlinks(domain: str) -> tuple[list[Backlink], str]:
    """Return (backlinks, data_source). Best-effort; never raises."""
    if not settings.BACKLINK_API_URL:
        return [], "unconfigured"

    try:
        params: dict[str, str] = {"domain": _host(domain)}
        if settings.BACKLINK_API_KEY:
            params["key"] = settings.BACKLINK_API_KEY
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT}, timeout=30.0
        ) as client:
            resp = await client.get(settings.BACKLINK_API_URL, params=params)
        if resp.status_code != 200:
            return [], "error"
        data = resp.json()
    except Exception:  # noqa: BLE001 - free APIs are flaky; degrade cleanly
        return [], "error"

    return _parse(data), settings.BACKLINK_PROVIDER


def _parse(data: object) -> list[Backlink]:
    """Map a provider response into Backlink objects.

    NOTE: OpenLinkProfiler's exact field names should be confirmed against
    their live API. We read a list of records from common container keys and
    accept several field-name aliases so the mapping is resilient.
    """
    records: list = []
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        for key in ("backlinks", "results", "data", "links"):
            if isinstance(data.get(key), list):
                records = data[key]
                break

    backlinks: list[Backlink] = []
    for rec in records[: settings.BACKLINK_MAX]:
        if not isinstance(rec, dict):
            continue
        source = (
            rec.get("source_url")
            or rec.get("url")
            or rec.get("from")
            or rec.get("link")
            or ""
        )
        if not source:
            continue
        anchor = (
            rec.get("anchor")
            or rec.get("anchor_text")
            or rec.get("text")
            or ""
        ).strip()
        # nofollow may be a bool, or inferred from a link_type/rel field.
        nofollow = bool(rec.get("nofollow"))
        rel = str(rec.get("rel") or rec.get("link_type") or "").lower()
        if "nofollow" in rel:
            nofollow = True
        backlinks.append(
            Backlink(
                source_url=source,
                source_domain=_host(source),
                anchor=anchor,
                nofollow=nofollow,
            )
        )
    return backlinks


# --- Profile aggregation ------------------------------------------------
async def get_profile(domain: str) -> BacklinkProfileResponse:
    backlinks, data_source = await _fetch_backlinks(domain)
    total = len(backlinks)
    referring = {b.source_domain for b in backlinks if b.source_domain}
    nofollow_count = sum(1 for b in backlinks if b.nofollow)
    follow_count = total - nofollow_count

    anchor_counter = Counter(b.anchor or "(empty)" for b in backlinks)
    anchor_distribution = [
        AnchorCount(
            anchor=anchor,
            count=count,
            percentage=round(count / total * 100, 1) if total else 0.0,
        )
        for anchor, count in anchor_counter.most_common(15)
    ]

    return BacklinkProfileResponse(
        domain=_host(domain),
        data_source=data_source,
        limited=data_source in ("unconfigured", "error", "openlinkprofiler"),
        referring_domains=len(referring),
        total_backlinks=total,
        follow_count=follow_count,
        nofollow_count=nofollow_count,
        nofollow_ratio=round(nofollow_count / total, 3) if total else 0.0,
        anchor_distribution=anchor_distribution,
        sample_backlinks=[
            SampleBacklink(
                source_url=b.source_url,
                source_domain=b.source_domain,
                anchor=b.anchor or "(empty)",
                nofollow=b.nofollow,
            )
            for b in backlinks[:25]
        ],
    )


# --- Broken Link Building -----------------------------------------------
async def find_broken_links(url: str) -> BrokenLinkResponse:
    if not urlparse(url).scheme:
        url = f"https://{url}"
    base_host = urlparse(url).netloc

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=settings.AUDIT_REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        from bs4 import BeautifulSoup

        resp = await client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        seen: set[str] = set()
        candidates: list[tuple[str, str, str]] = []  # (url, anchor, kind)
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith(
                ("#", "mailto:", "tel:", "javascript:")
            ):
                continue
            absolute = urljoin(str(resp.url), href)
            if urlparse(absolute).scheme not in ("http", "https"):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            kind = (
                "internal"
                if urlparse(absolute).netloc == base_host
                else "external"
            )
            candidates.append(
                (absolute, anchor.get_text(strip=True), kind)
            )
            if len(candidates) >= settings.BACKLINK_MAX_LINKS_CHECKED:
                break

        broken: list[BrokenOutboundLink] = []
        for link, text, kind in candidates:
            try:
                r = await client.head(link)
                if r.status_code >= 400:
                    r = await client.get(link, headers={"Range": "bytes=0-0"})
                if r.status_code >= 400:
                    broken.append(
                        BrokenOutboundLink(
                            url=link,
                            anchor=text or "(no anchor)",
                            status_code=r.status_code,
                            reason=f"HTTP {r.status_code}",
                            kind=kind,
                        )
                    )
            except httpx.HTTPError as exc:
                broken.append(
                    BrokenOutboundLink(
                        url=link,
                        anchor=text or "(no anchor)",
                        status_code=None,
                        reason=str(exc),
                        kind=kind,
                    )
                )

    return BrokenLinkResponse(
        url=str(resp.url),
        links_checked=len(candidates),
        broken_count=len(broken),
        broken_links=broken,
    )
