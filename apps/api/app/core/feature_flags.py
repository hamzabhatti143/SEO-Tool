"""Feature-based access control for the two subscription tiers.

Signup is invite-only and an admin assigns each account a tier:

* ``standard`` — every module EXCEPT the premium-only ones below.
* ``premium``  — every module unlocked.

This module is the single source of truth for which tier may use which
feature. The FastAPI ``require_feature`` dependency (see ``app.api.deps``)
and the ``report_service`` white-label check both consult it, and the
Next.js client mirrors ``PREMIUM_FEATURES`` in ``lib/feature-flags.ts``.
"""

from __future__ import annotations

STANDARD = "standard"
PREMIUM = "premium"
TIERS = frozenset({STANDARD, PREMIUM})

# Every gateable feature/module in the product. Keys are stable identifiers
# used by ``require_feature`` and the client; values are human labels used in
# the "Upgrade to Premium" message.
FEATURE_LABELS: dict[str, str] = {
    "website_audit": "Website Audit",
    "core_web_vitals": "Core Web Vitals",
    "fix_history": "Fix History",
    "on_page_optimizer": "On-Page Optimizer",
    "keyword_research": "Keyword Research",
    "competitor_intel": "Competitor Intelligence",
    "content_gaps": "Content Gaps",
    "internal_links": "Internal Links",
    "ai_content_studio": "AI Content Studio",
    "reports": "Reports",
    "backlink_center": "Backlink Center",
    "automation": "Automation",
    "agency_mode": "Agency Mode",
    "white_label": "White-label reports",
}

# Features reserved for the premium tier (denied on standard).
PREMIUM_FEATURES: frozenset[str] = frozenset(
    {"backlink_center", "automation", "agency_mode", "white_label"}
)

# tier -> the set of features that tier may access.
TIER_FEATURES: dict[str, frozenset[str]] = {
    STANDARD: frozenset(FEATURE_LABELS) - PREMIUM_FEATURES,
    PREMIUM: frozenset(FEATURE_LABELS),
}


def tier_allows(tier: str | None, feature: str) -> bool:
    """Whether ``tier`` may access ``feature`` (unknown tiers get standard)."""
    allowed = TIER_FEATURES.get(tier or STANDARD, TIER_FEATURES[STANDARD])
    return feature in allowed


def feature_label(feature: str) -> str:
    """Human-readable label for a feature id (falls back to the id)."""
    return FEATURE_LABELS.get(feature, feature.replace("_", " ").title())
