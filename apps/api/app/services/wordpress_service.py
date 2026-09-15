"""WordPress connector service.

Verifies a WordPress connection by calling the RankPilot plugin's health
check, and builds the endpoint URLs every later plugin call uses.

The plugin exposes the same actions over TWO transports:

  * REST  — GET/POST {site}/wp-json/{namespace}/{action}
            with ``Authorization: Bearer {api_key}``
  * AJAX  — GET/POST {site}/wp-admin/admin-ajax.php?action=rankpilot_{action}
            with the key as a ``rankpilot_key`` request parameter

Some hosts don't route ``/wp-json/`` correctly (a stray static index in the
web root, a proxy/CDN rule, permalinks not resolving) even though the site
otherwise works — but ``/wp-admin/admin-ajax.php`` is a real PHP file that is
reachable regardless. So ``check_connection`` tries REST first and transparently
falls back to admin-ajax, then records which transport succeeded so all
subsequent calls use the same one.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

from app.core.config import settings

# Some hosts / WAFs / CDNs block requests with non-browser User-Agents, which
# would make the plugin's endpoints look unreachable. Present a common
# desktop-Chrome UA so the rankpilot endpoints respond normally.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Canonical action tokens (underscore form). REST uses the hyphenated form in
# its route path; admin-ajax uses ``rankpilot_{action}`` verbatim.
Transport = str  # "rest" | "ajax"


@dataclass
class WordPressHealth:
    ok: bool
    detail: str
    site_url: str
    # Which transport the health check succeeded on ("rest" or "ajax"). On
    # failure this is the last transport attempted.
    transport: Transport = "rest"


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


def build_wp_endpoint(site_url: str, action: str, transport: Transport) -> str:
    """Build the plugin URL for ``action`` under the given transport.

    ``action`` is a canonical token: "health" | "snapshot" | "apply_fix" |
    "revert". REST turns underscores into hyphens for its route path; admin-ajax
    uses ``rankpilot_{action}`` as the ``action`` query parameter.
    """
    base = site_url.rstrip("/")
    if transport == "ajax":
        return f"{base}/wp-admin/admin-ajax.php?action=rankpilot_{action}"
    namespace = settings.WORDPRESS_API_NAMESPACE.strip("/")
    rest_action = action.replace("_", "-")
    return f"{base}/wp-json/{namespace}/{rest_action}"


def build_wp_request(
    site_url: str, action: str, transport: Transport, api_key: str
) -> tuple[str, dict[str, str]]:
    """Return the (url, headers) for a plugin call, per transport.

    REST carries the key in an ``Authorization: Bearer`` header. AJAX carries
    it as a ``rankpilot_key`` query parameter, because some AJAX/CDN setups
    strip the Authorization header (the plugin's auth accepts either).
    """
    url = build_wp_endpoint(site_url, action, transport)
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    if transport == "ajax":
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urlencode({'rankpilot_key': api_key})}"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    return url, headers


async def _probe_health(
    origin: str, api_key: str, transport: Transport
) -> WordPressHealth:
    """Call the plugin health check over one transport and classify the result."""
    url, headers = build_wp_request(origin, "health", transport, api_key)

    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=settings.WORDPRESS_CONNECT_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        return WordPressHealth(
            ok=False,
            detail=f"Could not reach {url}: {exc}.",
            site_url=origin,
            transport=transport,
        )

    if response.status_code in (401, 403):
        return WordPressHealth(
            ok=False,
            detail="The plugin rejected the API key (unauthorized).",
            site_url=origin,
            transport=transport,
        )
    if response.status_code == 404:
        return WordPressHealth(
            ok=False,
            detail="Health-check route not found.",
            site_url=origin,
            transport=transport,
        )
    if response.status_code >= 400:
        return WordPressHealth(
            ok=False,
            detail=f"Health-check failed (HTTP {response.status_code}).",
            site_url=origin,
            transport=transport,
        )

    try:
        body = response.json()
    except ValueError:
        return WordPressHealth(
            ok=False,
            detail="Health-check did not return JSON (is a proxy in the way?).",
            site_url=origin,
            transport=transport,
        )

    if isinstance(body, dict) and body.get("status") == "ok":
        return WordPressHealth(
            ok=True, detail="Connected.", site_url=origin, transport=transport
        )

    return WordPressHealth(
        ok=False,
        detail="Unexpected health-check response from the plugin.",
        site_url=origin,
        transport=transport,
    )


async def check_connection(site_url: str, api_key: str) -> WordPressHealth:
    """Verify the connection, trying REST first then the admin-ajax fallback.

    Returns the transport that succeeded so it can be persisted and reused for
    every later plugin call. If both fail, reports both so the user can see the
    site was reachable one way but not the other.
    """
    origin = normalize_site_url(site_url)

    rest = await _probe_health(origin, api_key, "rest")
    if rest.ok:
        return rest

    ajax = await _probe_health(origin, api_key, "ajax")
    if ajax.ok:
        return ajax

    # Both transports failed. Surface the most useful combined message.
    detail = (
        "Could not connect to the RankPilot plugin. "
        f"REST (/wp-json/): {rest.detail} "
        f"admin-ajax fallback: {ajax.detail} "
        "Check that the site is online and the RankPilot plugin is installed "
        "and active."
    )
    return WordPressHealth(
        ok=False, detail=detail, site_url=origin, transport="rest"
    )
