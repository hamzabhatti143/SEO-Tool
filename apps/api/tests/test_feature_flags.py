"""Unit tests for tier-based feature gating."""

import pytest
from fastapi import HTTPException

from app.api.deps import require_feature
from app.core import feature_flags
from app.models.user import User


def test_standard_denied_premium_features() -> None:
    for feature in ["backlink_center", "automation", "agency_mode", "white_label"]:
        assert feature_flags.tier_allows("premium", feature) is True
        assert feature_flags.tier_allows("standard", feature) is False


def test_standard_allows_core_modules() -> None:
    for feature in ["website_audit", "keyword_research", "reports"]:
        assert feature_flags.tier_allows("standard", feature) is True
        assert feature_flags.tier_allows("premium", feature) is True


def test_unknown_tier_defaults_to_standard() -> None:
    assert feature_flags.tier_allows(None, "keyword_research") is True
    assert feature_flags.tier_allows("mystery", "backlink_center") is False


@pytest.mark.asyncio
async def test_require_feature_blocks_standard_with_upgrade_message() -> None:
    dependency = require_feature("backlink_center")
    standard = User(email="s@example.com", hashed_password="x", plan="standard")
    with pytest.raises(HTTPException) as exc:
        await dependency(current_user=standard)
    assert exc.value.status_code == 403
    assert "Premium" in exc.value.detail


@pytest.mark.asyncio
async def test_require_feature_allows_premium() -> None:
    dependency = require_feature("automation")
    premium = User(email="p@example.com", hashed_password="x", plan="premium")
    assert await dependency(current_user=premium) is premium
