"""Shopify connector service — Admin API OAuth install flow.

Flow:
  1. ``build_install`` — the authenticated install endpoint produces a signed
     ``state`` (a short-lived JWT carrying the project id) and the Shopify
     authorize URL. The browser is sent there to grant the requested scopes.
  2. Shopify redirects back to our callback with ``code``, ``shop``, ``state``
     and an ``hmac``. ``verify_callback`` validates the HMAC signature and the
     signed state; ``exchange_code`` swaps the code for a permanent Admin API
     access token, which the caller stores (encrypted).

No Shopify SDK is used — the OAuth handshake is a couple of plain HTTP calls.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import ALGORITHM, decode_access_token

# Accept "shop", "shop.myshopify.com" — reject anything that isn't a plain
# myshopify subdomain to avoid open-redirect / SSRF style abuse.
_SHOP_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$")
_STATE_PURPOSE = "shopify_oauth"


class ShopifyError(Exception):
    """Raised when the OAuth handshake cannot be completed."""


@dataclass
class ShopifyCallback:
    project_id: uuid.UUID
    shop: str


def normalize_shop(raw: str) -> str:
    """Coerce user input into a canonical ``<name>.myshopify.com`` domain."""
    shop = raw.strip().lower()
    shop = re.sub(r"^https?://", "", shop).rstrip("/")
    if "." not in shop:
        shop = f"{shop}.myshopify.com"
    if not _SHOP_RE.match(shop):
        raise ShopifyError(
            "Enter a valid Shopify domain, e.g. my-store.myshopify.com"
        )
    return shop


def _redirect_uri() -> str:
    base = settings.APP_BASE_URL.rstrip("/")
    return f"{base}{settings.API_V1_PREFIX}/connectors/shopify/callback"


def _encode_state(project_id: uuid.UUID, shop: str) -> str:
    """A short-lived signed JWT proving an authenticated user began install."""
    payload = {
        "sub": str(project_id),
        "shop": shop,
        "purpose": _STATE_PURPOSE,
        "exp": datetime.now(timezone.utc)
        + timedelta(seconds=settings.SHOPIFY_STATE_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def build_install(project_id: uuid.UUID, shop: str) -> str:
    """Return the Shopify OAuth authorize URL for ``project_id`` + ``shop``."""
    if not settings.SHOPIFY_API_KEY:
        raise ShopifyError(
            "Shopify is not configured (missing SHOPIFY_API_KEY)."
        )
    shop_domain = normalize_shop(shop)
    state = _encode_state(project_id, shop_domain)
    query = urlencode(
        {
            "client_id": settings.SHOPIFY_API_KEY,
            "scope": settings.SHOPIFY_SCOPES,
            "redirect_uri": _redirect_uri(),
            "state": state,
            # Offline access token (default) — a permanent token for the shop.
        }
    )
    return f"https://{shop_domain}/admin/oauth/authorize?{query}"


def verify_callback(params: dict[str, str]) -> ShopifyCallback:
    """Validate the callback HMAC + signed state; return project id + shop."""
    shop = params.get("shop", "")
    if not _SHOP_RE.match(shop):
        raise ShopifyError("Invalid or missing shop parameter.")

    if not _verify_hmac(params):
        raise ShopifyError("HMAC validation failed — request is not from Shopify.")

    state = params.get("state", "")
    try:
        claims = decode_access_token(state)
    except JWTError as exc:
        raise ShopifyError("OAuth state is invalid or expired.") from exc

    if claims.get("purpose") != _STATE_PURPOSE or claims.get("shop") != shop:
        raise ShopifyError("OAuth state does not match this request.")

    try:
        project_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise ShopifyError("OAuth state is malformed.") from exc

    return ShopifyCallback(project_id=project_id, shop=shop)


def _verify_hmac(params: dict[str, str]) -> bool:
    """Verify Shopify's HMAC over the query params (all except ``hmac``)."""
    received = params.get("hmac")
    if not received:
        return False
    message = "&".join(
        f"{key}={params[key]}"
        for key in sorted(params)
        if key not in ("hmac", "signature")
    )
    digest = hmac.new(
        settings.SHOPIFY_API_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, received)


async def exchange_code(shop: str, code: str) -> str:
    """Exchange the OAuth ``code`` for a permanent Admin API access token."""
    url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": settings.SHOPIFY_API_KEY,
        "client_secret": settings.SHOPIFY_API_SECRET,
        "code": code,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise ShopifyError(f"Token exchange request failed: {exc}") from exc

    if response.status_code != 200:
        raise ShopifyError(
            f"Token exchange failed (HTTP {response.status_code})."
        )
    token = response.json().get("access_token")
    if not token:
        raise ShopifyError("Shopify did not return an access token.")
    return token
