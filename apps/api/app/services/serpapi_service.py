"""SerpApi client for SERP position lookups.

We use SerpApi (https://serpapi.com/) as the data source rather than
scraping Google directly — direct scraping violates Google's ToS and is
unreliable/blocked. SerpApi returns structured, ToS-compliant results.

IMPORTANT: this requires a SerpApi API key (`SERPAPI_API_KEY`). SerpApi's
FREE tier is roughly ~100 searches/month; beyond that it is paid. Each
tracked keyword consumes ONE search per check, so a daily cron over N
keywords uses ~N*30 searches/month — budget accordingly (e.g. 3 keywords
checked daily ≈ 90 searches/month, near the free-tier ceiling).

We deliberately depend only on httpx (no `google-search-results` SDK) to
keep the dependency surface small.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.core.config import settings

_ENDPOINT = "https://serpapi.com/search.json"


def is_configured() -> bool:
    """True if a SerpApi key is present (live lookups are possible)."""
    return bool(settings.SERPAPI_API_KEY)


def _normalize_host(value: str) -> str:
    host = urlparse(value if "://" in value else f"//{value}").netloc or value
    return host.lower().removeprefix("www.")


async def check_rank(keyword: str, domain: str) -> tuple[int | None, str | None]:
    """Return (absolute_position, url) of ``domain`` for ``keyword`` in Google
    organic results, or (None, None) if not found within the paginated depth
    (SERPAPI_PAGE_SIZE * SERPAPI_MAX_PAGES).

    Google deprecated num=100, so we paginate with `start` and compute the
    absolute position with a running counter (SerpApi's per-page `position`
    resets each page). Raises RuntimeError if not configured or a request
    fails.
    """
    if not is_configured():
        raise RuntimeError("SERPAPI_API_KEY is not set")

    target = _normalize_host(domain)
    page_size = settings.SERPAPI_PAGE_SIZE
    base_params = {
        "engine": settings.SERPAPI_ENGINE,
        "q": keyword,
        "num": page_size,
        "api_key": settings.SERPAPI_API_KEY,
        # Pin country/language/domain so results match the target region (US).
        "gl": settings.SERPAPI_GL,
        "hl": settings.SERPAPI_HL,
        "google_domain": settings.SERPAPI_GOOGLE_DOMAIN,
    }
    if settings.SERPAPI_LOCATION:
        base_params["location"] = settings.SERPAPI_LOCATION

    position = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for page in range(settings.SERPAPI_MAX_PAGES):
            params = {**base_params, "start": page * page_size}
            resp = await client.get(_ENDPOINT, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"SerpApi returned HTTP {resp.status_code}")
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(f"SerpApi error: {data['error']}")

            results = data.get("organic_results", [])
            if not results:
                break  # no more pages
            for result in results:
                link = result.get("link", "")
                if not link:
                    continue
                position += 1
                if _normalize_host(link) == target:
                    return position, link

    return None, None
