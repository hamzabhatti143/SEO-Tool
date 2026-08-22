"""Core Web Vitals detection engine (Website Audit → Performance).

Backed by the **Google PageSpeed Insights (PSI) API v5** — a plain HTTPS call,
no local browser. For a URL we request **all four Lighthouse categories**:

    GET …/pagespeedonline/v5/runPagespeed?url=<u>&strategy=<mobile|desktop>
        &category=performance&category=accessibility
        &category=best-practices&category=seo&key=<PAGESPEED_API_KEY>

and extract:

* **Lab timing metrics** — FCP, LCP, TBT, CLS, Speed Index — straight from
  ``lighthouseResult.audits`` (numericValue). We do NOT read
  ``interaction-to-next-paint`` from lab audits — INP does not exist in
  simulated runs.
* **Field INP** — only ``loadingExperience.metrics.INTERACTION_TO_NEXT_PAINT``
  (real Chrome-user data). ``None`` when unavailable — never a fake 0.
* **Category scores** — performance / accessibility / best-practices / seo
  (each ``score`` ×100).
* **Insights / Diagnostics / Passed** — each category's ``auditRefs`` audits
  classified: opportunities-with-savings → Insights, other failing/informational
  → Diagnostics, ``score == 1`` → Passed.
* **Screenshots** — the load-timeline thumbnails and the final screenshot.

For accuracy we run the call ``PAGESPEED_RUNS`` times (default 2) and store the
**median** of each metric plus every individual run for transparency. Rate
limits (free tier: 25k/day, 240/min) surface as HTTP 429 and are retried with
backoff. The key lives in ``PAGESPEED_API_KEY`` (env only, never hardcoded).
"""

from __future__ import annotations

import asyncio
import statistics
import uuid
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.core_web_vitals import CoreWebVitals
from app.schemas.core_web_vitals import (
    AuditItem,
    CategoryAudits,
    CoreWebVitalsReport,
    LabMetrics,
    RunMetrics,
    ScanMetadata,
    Screenshots,
)

_PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Our category key -> Lighthouse category key.
_CATEGORY_MAP: dict[str, str] = {
    "performance": "performance",
    "accessibility": "accessibility",
    "best_practices": "best-practices",
    "seo": "seo",
}

# Timing-metric audits are shown in the metrics grid, not the audit lists.
_METRIC_AUDIT_IDS = frozenset(
    {
        "first-contentful-paint",
        "largest-contentful-paint",
        "total-blocking-time",
        "cumulative-layout-shift",
        "speed-index",
        "interactive",
        "max-potential-fid",
        "first-meaningful-paint",
        "interaction-to-next-paint",
    }
)


class CoreWebVitalsError(RuntimeError):
    """Raised when the PageSpeed scan cannot be run or produced no report."""


async def run_pagespeed(
    url: str, strategy: str = "mobile"
) -> CoreWebVitalsReport:
    """Scan ``url`` ``PAGESPEED_RUNS`` times; return the merged/median report."""
    if "://" not in url:
        url = f"https://{url}"

    runs = max(1, settings.PAGESPEED_RUNS)
    raw: list[dict[str, Any]] = []
    last_error: CoreWebVitalsError | None = None
    for _ in range(runs):
        try:
            raw.append(await _call_pagespeed(url, strategy))
        except CoreWebVitalsError as exc:
            last_error = exc

    if not raw:
        raise last_error or CoreWebVitalsError("PageSpeed produced no result.")
    return _build_report(raw, strategy)


# ---------------------------------------------------------------------------
# Calling the PageSpeed Insights API (all categories, with 429 retry)
# ---------------------------------------------------------------------------


async def _call_pagespeed(url: str, strategy: str) -> dict[str, Any]:
    """GET runPagespeed for all four categories, retrying on 429 / 5xx."""
    params: list[tuple[str, str]] = [
        ("url", url),
        ("strategy", strategy),
        ("category", "performance"),
        ("category", "accessibility"),
        ("category", "best-practices"),
        ("category", "seo"),
    ]
    if settings.PAGESPEED_API_KEY:
        params.append(("key", settings.PAGESPEED_API_KEY))

    endpoint = settings.PAGESPEED_API_URL or _PSI_ENDPOINT
    attempts = max(1, settings.PAGESPEED_MAX_RETRIES + 1)
    last_detail = ""

    async with httpx.AsyncClient(timeout=settings.PAGESPEED_TIMEOUT) as client:
        for attempt in range(attempts):
            try:
                resp = await client.get(endpoint, params=params)
            except httpx.HTTPError as exc:
                last_detail = str(exc)
                if attempt + 1 < attempts:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise CoreWebVitalsError(
                    f"PageSpeed request failed: {last_detail}"
                ) from exc

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429 or resp.status_code >= 500:
                last_detail = _error_detail(resp)
                if attempt + 1 < attempts:
                    await asyncio.sleep(_retry_after(resp, attempt))
                    continue
                if resp.status_code == 429:
                    raise CoreWebVitalsError(
                        "PageSpeed rate limit hit (HTTP 429) after retries — "
                        "free tier allows 240/min, 25k/day. Configure/upgrade "
                        f"PAGESPEED_API_KEY. {last_detail}"
                    )
                raise CoreWebVitalsError(
                    f"PageSpeed server error (HTTP {resp.status_code}). "
                    f"{last_detail}"
                )

            raise CoreWebVitalsError(
                f"PageSpeed error (HTTP {resp.status_code}): {_error_detail(resp)}"
            )

    raise CoreWebVitalsError(f"PageSpeed request failed: {last_detail}")


def _backoff(attempt: int) -> float:
    return min(settings.PAGESPEED_RETRY_BASE_DELAY * (2**attempt), 30.0)


def _retry_after(resp: httpx.Response, attempt: int) -> float:
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), 60.0)
        except ValueError:
            pass
    return _backoff(attempt)


def _error_detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("error", {}).get("message", ""))[:300]
    except (ValueError, AttributeError):
        return resp.text[:200]


# ---------------------------------------------------------------------------
# Building the report (median across runs + classified audits)
# ---------------------------------------------------------------------------


def _build_report(
    raw: list[dict[str, Any]], strategy: str
) -> CoreWebVitalsReport:
    per_run = [_run_metrics(r) for r in raw]
    median = LabMetrics(
        fcp=_median([m.fcp for m in per_run]),
        lcp=_median([m.lcp for m in per_run]),
        tbt=_median([m.tbt for m in per_run]),
        cls=_median([m.cls for m in per_run], digits=3),
        speed_index=_median([m.speed_index for m in per_run]),
    )

    # Representative run for the qualitative data (audits/screenshots/etc.).
    rep = raw[0]
    lhr = rep.get("lighthouseResult", {}) or {}
    audits = lhr.get("audits", {}) or {}

    scores = _median_scores(raw)
    categories = {
        key: _category_audits(lhr, key, scores.get(key))
        for key in _CATEGORY_MAP
    }

    return CoreWebVitalsReport(
        strategy=strategy,  # type: ignore[arg-type]
        metrics=median,
        field_inp=_field_inp(rep.get("loadingExperience")),
        categories=categories,
        screenshots=_screenshots(audits),
        metadata=_metadata(lhr),
        runs=per_run,
        lcp_element=_lcp_element(audits),
    )


def _run_metrics(raw: dict[str, Any]) -> RunMetrics:
    lhr = raw.get("lighthouseResult", {}) or {}
    audits = lhr.get("audits", {}) or {}
    perf = lhr.get("categories", {}).get("performance", {}).get("score")
    return RunMetrics(
        fcp=_num(audits, "first-contentful-paint"),
        lcp=_num(audits, "largest-contentful-paint"),
        tbt=_num(audits, "total-blocking-time"),
        cls=_num(audits, "cumulative-layout-shift", digits=3),
        speed_index=_num(audits, "speed-index"),
        performance_score=_score(perf),
    )


def _median_scores(raw: list[dict[str, Any]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for our_key, lh_key in _CATEGORY_MAP.items():
        vals = [
            _score(
                (r.get("lighthouseResult", {}).get("categories", {}) or {})
                .get(lh_key, {})
                .get("score")
            )
            for r in raw
        ]
        out[our_key] = _median([v for v in vals])
    return out


def _category_audits(
    lhr: dict[str, Any], our_key: str, score: float | None
) -> CategoryAudits:
    cat = (lhr.get("categories", {}) or {}).get(_CATEGORY_MAP[our_key])
    audits = lhr.get("audits", {}) or {}
    if not isinstance(cat, dict):
        return CategoryAudits(score=score)

    insights: list[AuditItem] = []
    diagnostics: list[AuditItem] = []
    passed_titles: list[str] = []

    for ref in cat.get("auditRefs", []) or []:
        aid = ref.get("id")
        audit = audits.get(aid) if aid else None
        if not isinstance(audit, dict) or aid in _METRIC_AUDIT_IDS:
            continue
        sdm = audit.get("scoreDisplayMode")
        if sdm in ("manual", "notApplicable"):
            continue
        audit_score = audit.get("score")

        if audit_score == 1:
            passed_titles.append(str(audit.get("title", aid)))
        elif _is_opportunity(audit):
            insights.append(_audit_item(aid, audit))
        elif audit_score is not None and audit_score < 1:
            diagnostics.append(_audit_item(aid, audit))
        elif sdm == "informative":
            diagnostics.append(_audit_item(aid, audit))

    insights.sort(key=lambda a: -(a.savings_ms or a.savings_bytes or 0))
    diagnostics.sort(key=lambda a: (a.score if a.score is not None else 1))

    return CategoryAudits(
        score=score,
        insights=insights,
        diagnostics=diagnostics,
        passed_count=len(passed_titles),
        passed_titles=passed_titles[:250],
    )


def _is_opportunity(audit: dict[str, Any]) -> bool:
    details = audit.get("details") or {}
    return (
        details.get("type") == "opportunity"
        or audit.get("scoreDisplayMode") == "metricSavings"
    )


def _audit_item(aid: str, audit: dict[str, Any]) -> AuditItem:
    details = audit.get("details") or {}
    savings_ms = details.get("overallSavingsMs")
    if savings_ms is None:
        metric_savings = audit.get("metricSavings") or {}
        numeric = [v for v in metric_savings.values() if isinstance(v, int | float)]
        savings_ms = max(numeric) if numeric else None
    savings_bytes = details.get("overallSavingsBytes")
    return AuditItem(
        id=aid,
        title=str(audit.get("title", aid)),
        description=str(audit.get("description", "")),
        score=audit.get("score"),
        display_value=audit.get("displayValue"),
        savings_ms=round(savings_ms) if isinstance(savings_ms, int | float) else None,
        savings_bytes=int(savings_bytes)
        if isinstance(savings_bytes, int | float)
        else None,
    )


def _screenshots(audits: dict[str, Any]) -> Screenshots:
    items = (
        (audits.get("screenshot-thumbnails", {}) or {})
        .get("details", {})
        .get("items", [])
    )
    timeline = [
        it["data"]
        for it in items
        if isinstance(it, dict) and isinstance(it.get("data"), str)
    ]
    final = (
        (audits.get("final-screenshot", {}) or {}).get("details", {}).get("data")
    )
    return Screenshots(timeline=timeline, final=final)


def _metadata(lhr: dict[str, Any]) -> ScanMetadata:
    cfg = lhr.get("configSettings", {}) or {}
    return ScanMetadata(
        lighthouse_version=lhr.get("lighthouseVersion"),
        form_factor=cfg.get("formFactor"),
        throttling_method=cfg.get("throttlingMethod"),
        fetch_time=lhr.get("fetchTime"),
        final_url=lhr.get("finalDisplayedUrl")
        or lhr.get("finalUrl")
        or lhr.get("requestedUrl"),
    )


def _field_inp(loading_experience: Any) -> float | None:
    if not isinstance(loading_experience, dict):
        return None
    metric = (loading_experience.get("metrics") or {}).get(
        "INTERACTION_TO_NEXT_PAINT"
    )
    if not isinstance(metric, dict):
        return None
    value = metric.get("percentile")
    return float(value) if isinstance(value, int | float) else None


def _lcp_element(audits: dict[str, Any]) -> str | None:
    items = (
        (audits.get("largest-contentful-paint-element", {}) or {})
        .get("details", {})
        .get("items", [])
    )
    if not items:
        return None
    first = items[0]
    node = first.get("node") if isinstance(first.get("node"), dict) else first
    snippet = node.get("snippet") or node.get("nodeLabel") or node.get("selector")
    return str(snippet)[:1024] if snippet else None


def _num(
    audits: dict[str, Any], key: str, digits: int = 0
) -> float | None:
    audit = audits.get(key)
    if not isinstance(audit, dict):
        return None
    value = audit.get("numericValue")
    return round(float(value), digits) if isinstance(value, int | float) else None


def _score(raw: Any) -> float | None:
    return round(raw * 100) if isinstance(raw, int | float) else None


def _median(values: list[float | None], digits: int = 0) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return round(statistics.median(present), digits)


# ---------------------------------------------------------------------------
# Persistence (shared write path for the scan endpoint + fix orchestrator)
# ---------------------------------------------------------------------------


async def scan_and_store(
    db: AsyncSession, project_id: uuid.UUID, url: str, strategy: str = "mobile"
) -> CoreWebVitals:
    """Run a scan and persist a ``CoreWebVitals`` row."""
    report = await run_pagespeed(url, strategy)
    cats = report.categories
    scan = CoreWebVitals(
        project_id=project_id,
        url=url,
        strategy=strategy,
        fcp=report.metrics.fcp,
        lcp=report.metrics.lcp,
        tbt=report.metrics.tbt,
        cls=report.metrics.cls,
        speed_index=report.metrics.speed_index,
        field_inp=report.field_inp,
        performance_score=_cat_score(cats, "performance"),
        accessibility_score=_cat_score(cats, "accessibility"),
        best_practices_score=_cat_score(cats, "best_practices"),
        seo_score=_cat_score(cats, "seo"),
        report_json=report.model_dump(),
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan


def _cat_score(cats: dict[str, CategoryAudits], key: str) -> float | None:
    cat = cats.get(key)
    return cat.score if cat is not None else None
