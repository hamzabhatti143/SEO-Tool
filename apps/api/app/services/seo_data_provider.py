"""SEO data provider integration point (first-party metrics).

By default RankPilot uses **AI estimates** for traffic and authority, derived
only from publicly crawlable on-page signals. Those are clearly labeled and
are NOT measured analytics.

To surface *real* figures (organic traffic, domain authority/rank, referring
domains, ranked keywords) you connect a third-party SEO data API here. This
module is the single seam where that happens: :func:`get_domain_metrics`
returns ``None`` until a provider is configured, and returns
:class:`ProviderMetrics` once one is. Callers (competitor_service) check the
result and mark those figures ``source="provider"`` instead of
``"ai_estimate"``.

Wiring a provider — set ``SEO_PROVIDER`` + credentials in settings/.env:

* **DataForSEO** (recommended entry point) — pay-as-you-go REST, no
  enterprise contract. HTTP Basic auth with ``DATAFORSEO_LOGIN`` /
  ``DATAFORSEO_PASSWORD``. Useful endpoints:
    - ``/v3/backlinks/summary/live`` → referring domains, backlinks, rank.
    - ``/v3/dataforseo_labs/google/domain_rank_overview/live`` → estimated
      organic traffic + keyword count.
* **Ahrefs API** — requires an Ahrefs subscription with API access. Bearer
  token (``AHREFS_API_TOKEN``). Endpoints return Domain Rating (DR),
  backlinks, organic keywords/traffic.
* **Semrush API** — requires a subscription with API units
  (``SEMRUSH_API_KEY``, passed as ``?key=``). Returns Authority Score,
  organic traffic, and keyword data via the Analytics API.

To implement one: add an ``async def _fetch_<provider>(domain)`` that calls
the API with httpx, map its response into :class:`ProviderMetrics`, and
dispatch to it from :func:`get_domain_metrics` based on ``settings.SEO_PROVIDER``.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.core.config import settings


class ProviderMetrics(BaseModel):
    """First-party metrics for a domain from a real SEO data provider."""

    provider: str
    domain: str
    organic_traffic: int | None = None
    domain_authority: int | None = None  # DR / DA / Authority Score
    referring_domains: int | None = None
    backlinks: int | None = None
    ranked_keywords: int | None = None


async def get_domain_metrics(domain: str) -> ProviderMetrics | None:
    """Return real provider metrics for ``domain``, or ``None`` if no provider
    is configured (in which case callers fall back to AI estimates).

    No provider is wired by default. When ``settings.SEO_PROVIDER`` is set,
    dispatch to the matching adapter (see module docstring).
    """
    provider = (settings.SEO_PROVIDER or "").strip().lower()
    if not provider:
        return None

    # Integration point: implement and dispatch to a provider adapter here,
    # e.g.:
    #   if provider == "dataforseo":
    #       return await _fetch_dataforseo(domain)
    # Until an adapter is implemented, fall back to AI estimates.
    return None
