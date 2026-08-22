"""WordPress connector service.

Verifies a WordPress connection by calling the RankPilot plugin's REST
health-check route. The plugin (which the user installs on their site and
which generates the API key they paste into the UI) exposes:

    GET {site}/wp-json/{namespace}/health
        Authorization: Bearer {api_key}

and returns ``{"status": "ok", ...}`` when the key is valid. We only persist
credentials once this check passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx

from app.core.config import settings

_USER_AGENT = "RankPilotBot/0.1 (+https://rankpilot.ai/bot)"


@dataclass
class WordPressHealth:
    ok: bool
    detail: str
    site_url: str


def normalize_site_url(raw: str) -> str:
    """Return a clean ``scheme://host`` origin for the site (no path/slash)."""
    raw = raw.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise ValueError("Enter a valid site URL, e.g. https://example.com")
    # Keep only scheme + host (+ port); drop any path/query the user pasted.
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _health_url(site_url: str) -> str:
    namespace = settings.WORDPRESS_API_NAMESPACE.strip("/")
    return f"{site_url}/wp-json/{namespace}/health"


async def check_connection(site_url: str, api_key: str) -> WordPressHealth:
    """Call the plugin health-check; report whether the key/site are valid."""
    origin = normalize_site_url(site_url)
    url = _health_url(origin)

    try:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": _USER_AGENT,
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=settings.WORDPRESS_CONNECT_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        return WordPressHealth(
            ok=False,
            detail=(
                f"Could not reach {url}: {exc}. Is the site online and the "
                "RankPilot plugin installed?"
            ),
            site_url=origin,
        )

    if response.status_code in (401, 403):
        return WordPressHealth(
            ok=False,
            detail="The plugin rejected the API key (unauthorized).",
            site_url=origin,
        )
    if response.status_code == 404:
        return WordPressHealth(
            ok=False,
            detail=(
                "Health-check route not found. Install/activate the RankPilot "
                "WordPress plugin, then try again."
            ),
            site_url=origin,
        )
    if response.status_code >= 400:
        return WordPressHealth(
            ok=False,
            detail=f"Health-check failed (HTTP {response.status_code}).",
            site_url=origin,
        )

    try:
        body = response.json()
    except ValueError:
        return WordPressHealth(
            ok=False,
            detail="Health-check did not return JSON (is a proxy in the way?).",
            site_url=origin,
        )

    if isinstance(body, dict) and body.get("status") == "ok":
        return WordPressHealth(ok=True, detail="Connected.", site_url=origin)

    return WordPressHealth(
        ok=False,
        detail="Unexpected health-check response from the plugin.",
        site_url=origin,
    )
