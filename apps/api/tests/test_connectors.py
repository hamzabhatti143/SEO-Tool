"""Unit tests for the platform connector services (WordPress + Shopify).

These cover the security-critical OAuth pieces (HMAC verification, signed
state round-trip) and input normalization — no network calls.
"""

import hashlib
import hmac
import uuid

import pytest

from app.core import crypto
from app.core.config import settings
from app.services import shopify_service, wordpress_service
from app.services.shopify_service import ShopifyError


def test_crypto_round_trip() -> None:
    token = crypto.encrypt("super-secret-token")
    assert token != "super-secret-token"
    assert crypto.decrypt(token) == "super-secret-token"


def test_wordpress_normalize_site_url() -> None:
    assert (
        wordpress_service.normalize_site_url("example.com")
        == "https://example.com"
    )
    assert (
        wordpress_service.normalize_site_url("https://example.com/blog?x=1")
        == "https://example.com"
    )
    with pytest.raises(ValueError):
        wordpress_service.normalize_site_url("   ")


def test_build_wp_endpoint_rest_and_ajax(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WORDPRESS_API_NAMESPACE", "rankpilot/v1")
    site = "https://example.com"
    # REST uses the hyphenated action under /wp-json/{ns}/.
    assert (
        wordpress_service.build_wp_endpoint(site, "apply_fix", "rest")
        == "https://example.com/wp-json/rankpilot/v1/apply-fix"
    )
    assert (
        wordpress_service.build_wp_endpoint(site, "health", "rest")
        == "https://example.com/wp-json/rankpilot/v1/health"
    )
    # AJAX uses admin-ajax.php with the rankpilot_{action} query param.
    assert (
        wordpress_service.build_wp_endpoint(site, "apply_fix", "ajax")
        == "https://example.com/wp-admin/admin-ajax.php?action=rankpilot_apply_fix"
    )
    # A trailing slash on the site never doubles up.
    assert (
        wordpress_service.build_wp_endpoint(site + "/", "revert", "ajax")
        == "https://example.com/wp-admin/admin-ajax.php?action=rankpilot_revert"
    )


def test_build_wp_request_auth_by_transport() -> None:
    # REST carries the key in an Authorization: Bearer header, not the URL.
    url, headers = wordpress_service.build_wp_request(
        "https://example.com", "snapshot", "rest", "SECRETKEY"
    )
    assert headers["Authorization"] == "Bearer SECRETKEY"
    assert "rankpilot_key" not in url

    # AJAX carries the key as a rankpilot_key query param, no Authorization.
    url, headers = wordpress_service.build_wp_request(
        "https://example.com", "snapshot", "ajax", "SECRETKEY"
    )
    assert "Authorization" not in headers
    assert "action=rankpilot_snapshot" in url
    assert "rankpilot_key=SECRETKEY" in url

    # Both transports carry a same-origin Referer/Origin so a host WAF
    # (ModSecurity) doesn't 406 the POST.
    assert headers["Origin"] == "https://example.com"
    assert headers["Referer"].startswith("https://example.com")


async def test_check_connection_falls_back_to_ajax(monkeypatch) -> None:
    """REST failing should transparently try admin-ajax and report it."""
    seen: list[str] = []

    async def fake_probe(origin, api_key, transport):
        seen.append(transport)
        ok = transport == "ajax"  # REST fails, ajax succeeds
        return wordpress_service.WordPressHealth(
            ok=ok,
            detail="Connected." if ok else "boom",
            site_url=origin,
            transport=transport,
        )

    monkeypatch.setattr(wordpress_service, "_probe_health", fake_probe)
    health = await wordpress_service.check_connection("example.com", "KEY")
    assert health.ok is True
    assert health.transport == "ajax"
    assert seen == ["rest", "ajax"]  # tried REST first, then the fallback


def test_shopify_normalize_shop() -> None:
    assert shopify_service.normalize_shop("My-Store") == "my-store.myshopify.com"
    assert (
        shopify_service.normalize_shop("https://foo.myshopify.com/")
        == "foo.myshopify.com"
    )
    with pytest.raises(ShopifyError):
        shopify_service.normalize_shop("evil.example.com")


def test_shopify_build_install(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SHOPIFY_API_KEY", "test-key")
    url = shopify_service.build_install(uuid.uuid4(), "my-store")
    assert url.startswith("https://my-store.myshopify.com/admin/oauth/authorize?")
    assert "client_id=test-key" in url
    assert "read_themes" in url and "write_products" in url
    assert "state=" in url


def _sign(params: dict[str, str], secret: str) -> str:
    message = "&".join(
        f"{k}={params[k]}" for k in sorted(params) if k != "hmac"
    )
    return hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def test_shopify_verify_callback_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SHOPIFY_API_SECRET", "shh")
    project_id = uuid.uuid4()
    shop = "my-store.myshopify.com"
    state = shopify_service._encode_state(project_id, shop)

    params = {
        "shop": shop,
        "code": "auth-code",
        "state": state,
        "timestamp": "1700000000",
    }
    params["hmac"] = _sign(params, "shh")

    result = shopify_service.verify_callback(params)
    assert result.project_id == project_id
    assert result.shop == shop


def test_shopify_verify_callback_rejects_bad_hmac(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SHOPIFY_API_SECRET", "shh")
    state = shopify_service._encode_state(uuid.uuid4(), "my-store.myshopify.com")
    params = {
        "shop": "my-store.myshopify.com",
        "code": "auth-code",
        "state": state,
        "hmac": "deadbeef",
    }
    with pytest.raises(ShopifyError, match="HMAC"):
        shopify_service.verify_callback(params)


def test_shopify_verify_callback_rejects_tampered_shop(monkeypatch) -> None:
    """A valid state for shop A must not be reusable against shop B."""
    monkeypatch.setattr(settings, "SHOPIFY_API_SECRET", "shh")
    state = shopify_service._encode_state(uuid.uuid4(), "real.myshopify.com")
    params = {
        "shop": "attacker.myshopify.com",
        "code": "auth-code",
        "state": state,
        "timestamp": "1700000000",
    }
    params["hmac"] = _sign(params, "shh")  # valid HMAC, but state.shop differs
    with pytest.raises(ShopifyError, match="state"):
        shopify_service.verify_callback(params)
