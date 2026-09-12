"""Shopify technical-SEO fix handler (auto-confidence fixes).

Mirrors the WordPress plugin's snapshot → apply → revert contract, but drives
the **Shopify Admin API** (GraphQL + the REST Asset API) instead of a plugin.
Supports the same auto-confidence fix types the extended detector produces:

  * redirect_chain      — UrlRedirect resource: point the source path straight
                          at the final destination and collapse intermediate
                          redirects that formed the chain.
  * missing_canonical /
    incorrect_canonical — inject/correct a scoped <link rel="canonical"> in the
                          theme's Liquid (Asset API), guarded by a Liquid
                          conditional for the specific page.
  * missing_sitemap     — NOT APPLICABLE on Shopify (it manages /sitemap.xml
                          natively); reported as such, no change attempted.
  * broken_internal_link— find-and-replace the broken href in the resource's
                          body_html (product descriptionHtml / page.body /
                          article.body) via the *Update mutations.
  * mixed_content       — same find-and-replace, upgrading http:// → https://.
  * missing_alt_text    — set the media's alt via fileUpdate (AI alt text).

Backup / revert parity with the Core Web Vitals flow:
  * Theme-file edits snapshot the **exact asset value** before writing (the
    theme-backup-before-edit pattern, scoped to the file being touched) and
    revert by restoring it.
  * body_html edits snapshot the **original HTML** (content-level snapshot) and
    revert by restoring it.
  * redirect edits snapshot the affected redirect rows' prior state.

Every revert restores ``before_snapshot`` exactly, so Fix History "Revert"
behaves identically to CWV. NOTE: the Admin API calls follow Shopify's
documented API but are UNTESTED against a live store — verify on a dev store.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import InvalidToken, decrypt
from app.models.change_log import ChangeLog
from app.models.project import Project
from app.services import connector_service
from app.services.fix_service import FixError, FixHandlerResult

# Auto-confidence technical-SEO fix types this handler applies.
TECH_FIX_TYPES = frozenset(
    {
        "redirect_chain",
        "missing_canonical",
        "incorrect_canonical",
        "missing_sitemap",
        "broken_internal_link",
        "mixed_content",
        "missing_alt_text",
    }
)

# Theme layout that holds the <head> (where canonicals live).
_THEME_LAYOUT = "layout/theme.liquid"


def _canon_begin(key: str) -> str:
    # Liquid comment markers delimit our managed block (built by concatenation
    # so the Liquid `{%- … -%}` braces aren't treated as format fields).
    return "{%- comment -%} RankPilot canonical: " + key + " {%- endcomment -%}"


def _canon_end(key: str) -> str:
    return "{%- comment -%} /RankPilot canonical: " + key + " {%- endcomment -%}"

# GraphQL: which field carries body HTML per resource type, + its update op.
_BODY_FIELD = {
    "product": "descriptionHtml",
    "page": "body",
    "article": "body",
}


# ---------------------------------------------------------------------------
# Pure helpers (network-free, unit-tested)
# ---------------------------------------------------------------------------
def replace_href(html: str, broken: str, replacement: str) -> str:
    """Swap a broken href value for the replacement (href="…"/href='…')."""
    return html.replace(
        'href="' + broken + '"', 'href="' + replacement + '"'
    ).replace("href='" + broken + "'", "href='" + replacement + "'")


def upgrade_http(html: str, resources: list[str]) -> str:
    """Upgrade the given http:// resource URLs to https:// in ``html``."""
    for http in resources:
        http = str(http)
        if http.startswith("http://"):
            html = html.replace(http, "https://" + http[len("http://") :])
    return html


def redirect_path(url_or_path: str) -> str:
    """Normalize a URL/path to a Shopify redirect source path ('/slug')."""
    value = str(url_or_path).strip()
    if "://" in value:
        value = urlparse(value).path or "/"
    if not value.startswith("/"):
        value = "/" + value
    # Collapse a trailing slash (root stays "/").
    return value.rstrip("/") or "/"


def canonical_block(key: str, path: str, canonical: str) -> str:
    """A revertible, page-scoped canonical override for theme.liquid."""
    begin = _canon_begin(key)
    end = _canon_end(key)
    return (
        f"{begin}\n"
        f"{{%- if request.path == '{path}' -%}}"
        f'<link rel="canonical" href="{canonical}">'
        f"{{%- endif -%}}\n{end}"
    )


def inject_canonical(layout: str, key: str, path: str, canonical: str) -> str:
    """Insert (or replace) the managed canonical block just before </head>."""
    layout = remove_canonical(layout, key)
    block = canonical_block(key, path, canonical)
    lower = layout.lower()
    idx = lower.rfind("</head>")
    if idx == -1:
        return layout + "\n" + block
    return layout[:idx] + block + "\n" + layout[idx:]


def remove_canonical(layout: str, key: str) -> str:
    """Strip a previously-injected managed canonical block (idempotent)."""
    begin = _canon_begin(key)
    end = _canon_end(key)
    start = layout.find(begin)
    if start == -1:
        return layout
    stop = layout.find(end, start)
    if stop == -1:
        return layout
    stop += len(end)
    # Also swallow a trailing newline we added.
    if stop < len(layout) and layout[stop] == "\n":
        stop += 1
    return layout[:start] + layout[stop:]


# ---------------------------------------------------------------------------
# Admin API client
# ---------------------------------------------------------------------------
async def _shopify_creds(db: AsyncSession, project: Project) -> tuple[str, str]:
    """Return (shop_domain, access_token) for the project's Shopify connection."""
    cred = await connector_service.get_credentials(db, project.id)
    if cred is None or cred.platform != "shopify" or not cred.site_url:
        raise FixError(
            "No Shopify connection for this project. Connect the store first."
        )
    try:
        token = decrypt(cred.encrypted_api_key_or_token)
    except InvalidToken as exc:
        raise FixError(
            "Stored Shopify credentials could not be decrypted."
        ) from exc
    return cred.site_url.strip().rstrip("/"), token


def _headers(token: str) -> dict[str, str]:
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}


async def _gql(
    shop: str, token: str, query: str, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run a GraphQL Admin API call; raise FixError on transport/user errors."""
    url = f"https://{shop}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                url,
                headers=_headers(token),
                json={"query": query, "variables": variables or {}},
            )
    except httpx.HTTPError as exc:
        raise FixError(f"Could not reach the Shopify Admin API: {exc}") from exc
    if resp.status_code != 200:
        raise FixError(f"Shopify Admin API error (HTTP {resp.status_code}).")
    body = resp.json()
    if body.get("errors"):
        raise FixError(f"Shopify GraphQL error: {body['errors']}")
    return body.get("data") or {}


def _check_user_errors(payload: dict[str, Any], op: str) -> None:
    errors = (payload or {}).get("userErrors") or []
    if errors:
        raise FixError(f"Shopify {op} failed: {errors}")


async def _asset_get(
    shop: str, token: str, theme_id: str, key: str
) -> str | None:
    """Read a theme asset's value via the REST Asset API (None if absent)."""
    url = (
        f"https://{shop}/admin/api/{settings.SHOPIFY_API_VERSION}"
        f"/themes/{theme_id}/assets.json"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                url, headers=_headers(token), params={"asset[key]": key}
            )
    except httpx.HTTPError as exc:
        raise FixError(f"Could not read theme asset: {exc}") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise FixError(f"Asset read failed (HTTP {resp.status_code}).")
    return (resp.json().get("asset") or {}).get("value")


async def _asset_put(
    shop: str, token: str, theme_id: str, key: str, value: str
) -> None:
    """Write a theme asset value via the REST Asset API."""
    url = (
        f"https://{shop}/admin/api/{settings.SHOPIFY_API_VERSION}"
        f"/themes/{theme_id}/assets.json"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.put(
                url,
                headers=_headers(token),
                json={"asset": {"key": key, "value": value}},
            )
    except httpx.HTTPError as exc:
        raise FixError(f"Could not write theme asset: {exc}") from exc
    if resp.status_code not in (200, 201):
        raise FixError(f"Asset write failed (HTTP {resp.status_code}).")


async def _main_theme_id(shop: str, token: str) -> str:
    """Return the id of the published ('main') theme."""
    url = f"https://{shop}/admin/api/{settings.SHOPIFY_API_VERSION}/themes.json"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                url, headers=_headers(token), params={"role": "main"}
            )
    except httpx.HTTPError as exc:
        raise FixError(f"Could not list themes: {exc}") from exc
    if resp.status_code != 200:
        raise FixError(f"Theme lookup failed (HTTP {resp.status_code}).")
    themes = resp.json().get("themes") or []
    if not themes:
        raise FixError("No published Shopify theme found.")
    return str(themes[0]["id"])


# ---------------------------------------------------------------------------
# Per-fix apply implementations
# ---------------------------------------------------------------------------
async def _apply_redirect(
    shop: str, token: str, target: str, data: dict[str, Any]
) -> tuple[str | None, dict, dict]:
    """Point source → final; collapse intermediate hops. Returns (handle, before, after)."""
    source = redirect_path(target)
    final = str(data.get("final_url") or data.get("final_path") or "")
    if not final:
        raise FixError("redirect_chain requires data.final_url.")

    async def find(path: str) -> dict | None:
        q = 'path:"' + path + '"'
        data_ = await _gql(
            shop,
            token,
            "query($q:String!){urlRedirects(first:1,query:$q)"
            "{edges{node{id path target}}}}",
            {"q": q},
        )
        edges = ((data_.get("urlRedirects") or {}).get("edges")) or []
        return edges[0]["node"] if edges else None

    before: dict[str, Any] = {"source": None, "intermediates": []}

    existing = await find(source)
    if existing:
        before["source"] = {"id": existing["id"], "target": existing["target"], "created": False}
        res = await _gql(
            shop,
            token,
            "mutation($id:ID!,$r:UrlRedirectInput!){urlRedirectUpdate(id:$id,"
            "urlRedirect:$r){urlRedirect{id path target}userErrors{field message}}}",
            {"id": existing["id"], "r": {"path": source, "target": final}},
        )
        _check_user_errors(res.get("urlRedirectUpdate"), "urlRedirectUpdate")
        handle = existing["id"]
    else:
        res = await _gql(
            shop,
            token,
            "mutation($r:UrlRedirectInput!){urlRedirectCreate(urlRedirect:$r)"
            "{urlRedirect{id path target}userErrors{field message}}}",
            {"r": {"path": source, "target": final}},
        )
        _check_user_errors(res.get("urlRedirectCreate"), "urlRedirectCreate")
        node = (res.get("urlRedirectCreate") or {}).get("urlRedirect") or {}
        handle = node.get("id")
        before["source"] = {"id": handle, "target": None, "created": True}

    # Collapse intermediate redirects that formed the chain onto the final dest.
    for hop in data.get("chain") or []:
        hop_path = redirect_path(str(hop))
        if hop_path in (source, redirect_path(final)):
            continue
        node = await find(hop_path)
        if not node:
            continue
        before["intermediates"].append({"id": node["id"], "target": node["target"]})
        res = await _gql(
            shop,
            token,
            "mutation($id:ID!,$r:UrlRedirectInput!){urlRedirectUpdate(id:$id,"
            "urlRedirect:$r){urlRedirect{id}userErrors{field message}}}",
            {"id": node["id"], "r": {"path": hop_path, "target": final}},
        )
        _check_user_errors(res.get("urlRedirectUpdate"), "urlRedirectUpdate")

    after = {"source": source, "target": final, "intermediates_collapsed": len(before["intermediates"])}
    return handle, before, after


async def _apply_canonical(
    shop: str, token: str, target: str, data: dict[str, Any]
) -> tuple[str | None, dict, dict]:
    theme_id = await _main_theme_id(shop, token)
    original = await _asset_get(shop, token, theme_id, _THEME_LAYOUT)
    if original is None:
        raise FixError("Could not read the theme's layout/theme.liquid.")
    path = redirect_path(target)
    canonical = str(data.get("canonical") or target)
    key = path.strip("/").replace("/", "-") or "home"
    new_value = inject_canonical(original, key, path, canonical)
    await _asset_put(shop, token, theme_id, _THEME_LAYOUT, new_value)
    before = {"theme_id": theme_id, "asset_key": _THEME_LAYOUT, "value": original}
    after = {"theme_id": theme_id, "asset_key": _THEME_LAYOUT, "canonical": canonical, "path": path}
    return f"{theme_id}:{_THEME_LAYOUT}", before, after


async def _resource_body(shop: str, token: str, gid: str, rtype: str) -> str:
    field = _BODY_FIELD[rtype]
    root = rtype  # product | page | article
    data = await _gql(
        shop,
        token,
        f"query($id:ID!){{{root}(id:$id){{id {field}}}}}",
        {"id": gid},
    )
    node = data.get(root) or {}
    return str(node.get(field) or "")


async def _update_resource_body(
    shop: str, token: str, gid: str, rtype: str, html: str
) -> None:
    field = _BODY_FIELD[rtype]
    if rtype == "product":
        res = await _gql(
            shop,
            token,
            "mutation($input:ProductInput!){productUpdate(input:$input)"
            "{product{id}userErrors{field message}}}",
            {"input": {"id": gid, field: html}},
        )
        _check_user_errors(res.get("productUpdate"), "productUpdate")
    elif rtype == "page":
        res = await _gql(
            shop,
            token,
            "mutation($id:ID!,$page:PageUpdateInput!){pageUpdate(id:$id,page:$page)"
            "{page{id}userErrors{field message}}}",
            {"id": gid, "page": {field: html}},
        )
        _check_user_errors(res.get("pageUpdate"), "pageUpdate")
    elif rtype == "article":
        res = await _gql(
            shop,
            token,
            "mutation($id:ID!,$article:ArticleUpdateInput!){articleUpdate(id:$id,"
            "article:$article){article{id}userErrors{field message}}}",
            {"id": gid, "article": {field: html}},
        )
        _check_user_errors(res.get("articleUpdate"), "articleUpdate")
    else:
        raise FixError(f"Unsupported resource_type '{rtype}'.")


async def _apply_body_edit(
    shop: str, token: str, target: str, data: dict[str, Any], fix_type: str
) -> tuple[str | None, dict, dict]:
    rtype = str(data.get("resource_type") or "product")
    gid = str(data.get("resource_id") or target)
    if rtype not in _BODY_FIELD:
        raise FixError(f"Unsupported resource_type '{rtype}'.")
    original = await _resource_body(shop, token, gid, rtype)
    if fix_type == "broken_internal_link":
        broken = str(data.get("broken_url") or "")
        replacement = str(data.get("replacement_url") or "")
        if not broken or not replacement:
            raise FixError("broken_internal_link requires broken_url + replacement_url.")
        new_html = replace_href(original, broken, replacement)
    else:  # mixed_content
        resources = data.get("resources") or []
        if not resources:
            raise FixError("mixed_content requires a non-empty resources list.")
        new_html = upgrade_http(original, list(resources))
    await _update_resource_body(shop, token, gid, rtype, new_html)
    before = {"resource_type": rtype, "resource_id": gid, "body_html": original}
    after = {"resource_type": rtype, "resource_id": gid}
    return gid, before, after


async def _apply_alt(
    shop: str, token: str, target: str, data: dict[str, Any]
) -> tuple[str | None, dict, dict]:
    gid = str(data.get("media_id") or data.get("resource_id") or target)
    alt = str(data.get("alt") or "")
    if not alt:
        raise FixError("missing_alt_text requires data.alt.")
    read = await _gql(
        shop,
        token,
        "query($id:ID!){node(id:$id){... on MediaImage{id alt}}}",
        {"id": gid},
    )
    original_alt = ((read.get("node") or {}).get("alt")) or ""
    res = await _gql(
        shop,
        token,
        "mutation($files:[FileUpdateInput!]!){fileUpdate(files:$files)"
        "{files{... on MediaImage{id alt}}userErrors{field message}}}",
        {"files": [{"id": gid, "alt": alt}]},
    )
    _check_user_errors(res.get("fileUpdate"), "fileUpdate")
    before = {"media_id": gid, "alt": original_alt}
    after = {"media_id": gid, "alt": alt}
    return gid, before, after


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------
async def apply_technical_fix(
    db: AsyncSession,
    project: Project,
    fix_type: str,
    target: str,
    data: dict[str, Any] | None = None,
) -> FixHandlerResult:
    """Apply one auto-confidence technical-SEO fix to the Shopify store."""
    if fix_type not in TECH_FIX_TYPES:
        raise FixError(f"Unsupported Shopify fix_type '{fix_type}'.")
    data = data or {}

    # Shopify manages /sitemap.xml itself — nothing to fix.
    if fix_type == "missing_sitemap":
        return FixHandlerResult(
            external_change_id=None,
            issue_type=fix_type,
            before_snapshot={"not_applicable": True},
            after_snapshot={"not_applicable": True},
            detail="Not applicable (Shopify manages sitemaps automatically).",
        )

    shop, token = await _shopify_creds(db, project)

    if fix_type == "redirect_chain":
        handle, before, after = await _apply_redirect(shop, token, target, data)
    elif fix_type in ("missing_canonical", "incorrect_canonical"):
        handle, before, after = await _apply_canonical(shop, token, target, data)
    elif fix_type in ("broken_internal_link", "mixed_content"):
        handle, before, after = await _apply_body_edit(
            shop, token, target, data, fix_type
        )
    elif fix_type == "missing_alt_text":
        handle, before, after = await _apply_alt(shop, token, target, data)
    else:  # pragma: no cover - guarded above
        raise FixError(f"Unsupported Shopify fix_type '{fix_type}'.")

    return FixHandlerResult(
        external_change_id=handle,
        issue_type=fix_type,
        before_snapshot=before,
        after_snapshot=after,
        detail=f"Applied Shopify {fix_type} fix.",
    )


async def revert_technical_fix(
    db: AsyncSession, project: Project, change: ChangeLog
) -> FixHandlerResult:
    """Revert a Shopify technical-SEO fix by restoring its before-snapshot."""
    fix_type = change.issue_type
    before = change.before_snapshot or {}

    if fix_type == "missing_sitemap" or before.get("not_applicable"):
        return FixHandlerResult(
            external_change_id=change.external_change_id,
            issue_type=fix_type,
            before_snapshot=change.after_snapshot,
            after_snapshot=change.before_snapshot,
            detail="Nothing to revert (not applicable on Shopify).",
        )

    shop, token = await _shopify_creds(db, project)

    if fix_type == "redirect_chain":
        await _revert_redirect(shop, token, before)
    elif fix_type in ("missing_canonical", "incorrect_canonical"):
        await _asset_put(
            shop, token, before["theme_id"], before["asset_key"], before["value"]
        )
    elif fix_type in ("broken_internal_link", "mixed_content"):
        await _update_resource_body(
            shop, token, before["resource_id"], before["resource_type"],
            before["body_html"],
        )
    elif fix_type == "missing_alt_text":
        await _gql(
            shop,
            token,
            "mutation($files:[FileUpdateInput!]!){fileUpdate(files:$files)"
            "{files{... on MediaImage{id}}userErrors{field message}}}",
            {"files": [{"id": before["media_id"], "alt": before.get("alt", "")}]},
        )
    else:
        raise FixError(f"Cannot revert unsupported fix_type '{fix_type}'.")

    return FixHandlerResult(
        external_change_id=change.external_change_id,
        issue_type=fix_type,
        before_snapshot=change.after_snapshot,
        after_snapshot=change.before_snapshot,
        detail=f"Reverted Shopify {fix_type} fix.",
    )


async def _revert_redirect(shop: str, token: str, before: dict[str, Any]) -> None:
    src = before.get("source") or {}
    if src.get("created") and src.get("id"):
        # We created it — delete it.
        res = await _gql(
            shop,
            token,
            "mutation($id:ID!){urlRedirectDelete(id:$id)"
            "{deletedRedirectId userErrors{field message}}}",
            {"id": src["id"]},
        )
        _check_user_errors(res.get("urlRedirectDelete"), "urlRedirectDelete")
    elif src.get("id") and src.get("target") is not None:
        # Restore its prior target.
        res = await _gql(
            shop,
            token,
            "mutation($id:ID!,$r:UrlRedirectInput!){urlRedirectUpdate(id:$id,"
            "urlRedirect:$r){urlRedirect{id}userErrors{field message}}}",
            {"id": src["id"], "r": {"target": src["target"]}},
        )
        _check_user_errors(res.get("urlRedirectUpdate"), "urlRedirectUpdate")
    for hop in before.get("intermediates") or []:
        res = await _gql(
            shop,
            token,
            "mutation($id:ID!,$r:UrlRedirectInput!){urlRedirectUpdate(id:$id,"
            "urlRedirect:$r){urlRedirect{id}userErrors{field message}}}",
            {"id": hop["id"], "r": {"target": hop["target"]}},
        )
        _check_user_errors(res.get("urlRedirectUpdate"), "urlRedirectUpdate")
