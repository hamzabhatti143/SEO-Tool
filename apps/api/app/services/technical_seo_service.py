"""Technical-SEO analysis: structured data, robots.txt, and llms.txt.

Runs as part of the Website Audit scan (``tasks.task_run_audit``): for the
audited page it detects + validates schema.org markup, and for the site root it
fetches and analyzes ``robots.txt`` and ``llms.txt``. Each run replaces the
project's previous rows so the tables reflect the current state.

The parse/validate helpers are pure functions (HTML/text in, results out) so
they're unit-testable without a network.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.technical_seo import LlmsTxtAudit, RobotsAudit, SchemaAudit
from app.schemas.technical_seo import TechnicalSeoResponse

_USER_AGENT = "RankPilotBot/0.1 (+https://rankpilot.ai/bot)"
_MAX_SCHEMAS = 50

# schema.org type → required properties (mirrors Google's rich-result
# essentials). Drives is_valid; unknown types are recorded but not failed
# (we don't flag requirements we don't know).
_REQUIRED_PROPS: dict[str, list[str]] = {
    "Organization": ["name"],
    "LocalBusiness": ["name", "address"],
    "Article": ["headline"],
    "NewsArticle": ["headline"],
    "BlogPosting": ["headline"],
    "Product": ["name"],
    "Offer": ["price", "priceCurrency"],
    "FAQPage": ["mainEntity"],
    "QAPage": ["mainEntity"],
    "BreadcrumbList": ["itemListElement"],
    "Recipe": ["name", "recipeIngredient", "recipeInstructions"],
    "Event": ["name", "startDate", "location"],
    "Review": ["reviewRating", "author"],
    "Person": ["name"],
    "WebSite": ["name", "url"],
    "WebPage": ["name"],
    "VideoObject": ["name", "description", "thumbnailUrl", "uploadDate"],
    "HowTo": ["name", "step"],
}


# ---------------------------------------------------------------------------
# Structured data (schema.org)
# ---------------------------------------------------------------------------


def analyze_schema(html: str) -> list[dict[str, Any]]:
    """Detect + validate JSON-LD, Microdata, and RDFa blocks in ``html``."""
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict[str, Any]] = []
    results.extend(_json_ld(soup))
    results.extend(_microdata(soup))
    results.extend(_rdfa(soup))
    return results[:_MAX_SCHEMAS]


def _json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            out.append(
                {
                    "schema_type": "Unknown",
                    "fmt": "json-ld",
                    "is_valid": False,
                    "missing_properties": ["(invalid JSON — could not parse)"],
                    "raw_schema": {"raw": raw[:2000]},
                }
            )
            continue
        for obj in _iter_ld_objects(data):
            if isinstance(obj, dict):
                out.append(_evaluate_ld(obj))
    return out


def _iter_ld_objects(data: Any) -> list[Any]:
    """Flatten a JSON-LD payload into individual schema objects (@graph/lists)."""
    items: list[Any] = []
    if isinstance(data, list):
        for entry in data:
            items.extend(_iter_ld_objects(entry))
    elif isinstance(data, dict):
        if isinstance(data.get("@graph"), list):
            for entry in data["@graph"]:
                items.extend(_iter_ld_objects(entry))
        else:
            items.append(data)
    return items


def _evaluate_ld(obj: dict[str, Any]) -> dict[str, Any]:
    schema_type = _type_name(obj.get("@type"))
    present = {k for k in obj if not k.startswith("@")}
    is_valid, missing = _validate(schema_type, present)
    return {
        "schema_type": schema_type,
        "fmt": "json-ld",
        "is_valid": is_valid,
        "missing_properties": missing,
        "raw_schema": obj,
    }


def _microdata(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in soup.find_all(attrs={"itemscope": True}):
        itemtype = node.get("itemtype")
        if not itemtype or "schema.org" not in _first(itemtype):
            continue
        schema_type = _type_name(itemtype)
        props = {
            _first(child.get("itemprop"))
            for child in node.find_all(attrs={"itemprop": True})
            if child.get("itemprop")
        }
        is_valid, missing = _validate(schema_type, props)
        out.append(
            {
                "schema_type": schema_type,
                "fmt": "microdata",
                "is_valid": is_valid,
                "missing_properties": missing,
                "raw_schema": {
                    "itemtype": _first(itemtype),
                    "properties": sorted(props),
                },
            }
        )
    return out


def _rdfa(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in soup.find_all(attrs={"typeof": True}):
        schema_type = _type_name(node.get("typeof"))
        if not schema_type or schema_type == "Unknown":
            continue
        props = {
            _first(child.get("property"))
            for child in node.find_all(attrs={"property": True})
            if child.get("property")
        }
        is_valid, missing = _validate(schema_type, props)
        out.append(
            {
                "schema_type": schema_type,
                "fmt": "rdfa",
                "is_valid": is_valid,
                "missing_properties": missing,
                "raw_schema": {
                    "typeof": node.get("typeof"),
                    "properties": sorted(props),
                },
            }
        )
    return out


def _type_name(raw: Any) -> str:
    """Normalize an @type/itemtype/typeof value to a bare schema.org type."""
    value = _first(raw)
    if not value:
        return "Unknown"
    # Strip a schema.org URL or vocab prefix, keep the last path/colon segment.
    value = value.rstrip("/").split("/")[-1].split(":")[-1]
    return value or "Unknown"


def _first(raw: Any) -> str:
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw) if raw is not None else ""


def _validate(schema_type: str, present: set[str]) -> tuple[bool, list[str]]:
    required = _REQUIRED_PROPS.get(schema_type, [])
    missing = [prop for prop in required if prop not in present]
    return (not missing), missing


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------

_ASSET_BLOCK_RE = re.compile(r"\.(?:css|js)(?:$|[?*])", re.IGNORECASE)
_ASSET_DIRS = ("/wp-content/", "/wp-includes/", "/assets/", "/static/", "/css/", "/js/")


def analyze_robots(content: str) -> dict[str, Any]:
    """Parse robots.txt into user-agent groups + sitemap directives."""
    groups: list[dict[str, Any]] = []
    sitemaps: list[str] = []
    current: dict[str, Any] | None = None

    for raw in content.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            current = {"user_agent": value or "*", "disallow": [], "allow": []}
            groups.append(current)
        elif field == "disallow":
            if current is None:
                current = {"user_agent": "*", "disallow": [], "allow": []}
                groups.append(current)
            current["disallow"].append(value)
        elif field == "allow":
            if current is None:
                current = {"user_agent": "*", "disallow": [], "allow": []}
                groups.append(current)
            current["allow"].append(value)
        elif field == "sitemap":
            if value:
                sitemaps.append(value)

    return {"user_agents": groups, "sitemaps": sitemaps}


def robots_issues(parsed: dict[str, Any], exists: bool) -> list[dict[str, str]]:
    """Flag common robots.txt problems."""
    if not exists:
        return [
            {
                "code": "missing",
                "severity": "warning",
                "message": (
                    "robots.txt is missing (404). Crawlers assume everything is "
                    "allowed, but you can't declare a Sitemap or crawl rules here."
                ),
            }
        ]

    issues: list[dict[str, str]] = []
    all_disallows: list[str] = []
    for group in parsed.get("user_agents", []):
        all_disallows.extend(group.get("disallow", []))
        if "/" in group.get("disallow", []):
            issues.append(
                {
                    "code": "blocks_site",
                    "severity": "critical",
                    "message": (
                        f"'Disallow: /' for user-agent '{group['user_agent']}' "
                        "blocks the entire site from being crawled."
                    ),
                }
            )

    blocked_assets = [
        d for d in all_disallows if _ASSET_BLOCK_RE.search(d) or d in _ASSET_DIRS
    ]
    if blocked_assets:
        issues.append(
            {
                "code": "blocks_assets",
                "severity": "warning",
                "message": (
                    "Rules may block CSS/JS resources ("
                    + ", ".join(sorted(set(blocked_assets))[:3])
                    + "), which can hurt how Google renders and ranks pages."
                ),
            }
        )

    if not parsed.get("sitemaps"):
        issues.append(
            {
                "code": "no_sitemap",
                "severity": "info",
                "message": (
                    "No Sitemap directive found. Add "
                    "'Sitemap: https://…/sitemap.xml' so crawlers discover URLs."
                ),
            }
        )
    return issues


# ---------------------------------------------------------------------------
# llms.txt
# ---------------------------------------------------------------------------


def analyze_llms(content: str) -> bool:
    """True when the content roughly follows the llms.txt markdown spec.

    Spec: an H1 title first, optional blockquote summary, then H2 sections that
    link to key pages. We check: starts with an H1, has at least one H2, and
    contains links.
    """
    lines = content.splitlines()
    non_empty = [ln.strip() for ln in lines if ln.strip()]
    if not non_empty:
        return False
    starts_with_h1 = non_empty[0].startswith("# ")
    has_h2 = any(ln.strip().startswith("## ") for ln in lines)
    has_links = any(
        ("](" in ln) or ("http://" in ln) or ("https://" in ln) for ln in lines
    )
    return starts_with_h1 and has_h2 and has_links


# ---------------------------------------------------------------------------
# Fetch + store (the audit-scan entrypoint)
# ---------------------------------------------------------------------------


async def _fetch_text(
    client: httpx.AsyncClient, url: str
) -> tuple[bool, str | None]:
    """Return (exists, content). exists is True only on a 200 response."""
    try:
        resp = await client.get(url)
    except httpx.HTTPError:
        return False, None
    if resp.status_code == 200 and resp.text.strip():
        return True, resp.text
    return False, None


async def run_and_store(
    db: AsyncSession, project_id: uuid.UUID, page_url: str
) -> None:
    """Analyze the page + site root and replace the project's technical rows."""
    if "://" not in page_url:
        page_url = f"https://{page_url}"
    parsed = urlparse(page_url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=settings.AUDIT_REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        try:
            page_html: str | None = (await client.get(page_url)).text
        except httpx.HTTPError:
            page_html = None
        robots_exists, robots_content = await _fetch_text(client, f"{root}/robots.txt")
        llms_exists, llms_content = await _fetch_text(client, f"{root}/llms.txt")

    schemas = analyze_schema(page_html) if page_html else []
    robots_parsed = (
        analyze_robots(robots_content or "")
        if robots_exists
        else {"user_agents": [], "sitemaps": []}
    )
    issues = robots_issues(robots_parsed, robots_exists)
    llms_follows = analyze_llms(llms_content or "") if llms_exists else False

    # --- Replace previous rows (current-state, not history) ---
    await db.execute(
        delete(SchemaAudit).where(
            SchemaAudit.project_id == project_id,
            SchemaAudit.page_url == page_url,
        )
    )
    for item in schemas:
        db.add(
            SchemaAudit(
                project_id=project_id,
                page_url=page_url,
                schema_type=item["schema_type"],
                fmt=item["fmt"],
                is_valid=item["is_valid"],
                missing_properties=item["missing_properties"],
                raw_schema=_jsonable(item["raw_schema"]),
            )
        )

    await db.execute(
        delete(RobotsAudit).where(RobotsAudit.project_id == project_id)
    )
    db.add(
        RobotsAudit(
            project_id=project_id,
            exists=robots_exists,
            raw_content=robots_content,
            parsed_rules=robots_parsed,
            issues_found=issues,
        )
    )

    await db.execute(
        delete(LlmsTxtAudit).where(LlmsTxtAudit.project_id == project_id)
    )
    db.add(
        LlmsTxtAudit(
            project_id=project_id,
            exists=llms_exists,
            raw_content=llms_content,
            follows_spec_format=llms_follows,
        )
    )

    await db.commit()


def _jsonable(value: Any) -> Any:
    """Ensure a schema block is JSON-serializable for JSONB storage."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return {"note": "schema was not JSON-serializable", "repr": str(value)[:2000]}


async def get_technical_seo(
    db: AsyncSession, project_id: uuid.UUID
) -> TechnicalSeoResponse:
    """Return the project's current technical-SEO audit rows for the UI."""
    schema_rows = (
        await db.execute(
            select(SchemaAudit)
            .where(SchemaAudit.project_id == project_id)
            .order_by(SchemaAudit.page_url, SchemaAudit.schema_type)
        )
    ).scalars().all()
    robots = (
        await db.execute(
            select(RobotsAudit)
            .where(RobotsAudit.project_id == project_id)
            .order_by(RobotsAudit.checked_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    llms = (
        await db.execute(
            select(LlmsTxtAudit)
            .where(LlmsTxtAudit.project_id == project_id)
            .order_by(LlmsTxtAudit.checked_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return TechnicalSeoResponse(
        schema_audits=list(schema_rows), robots=robots, llms=llms
    )
