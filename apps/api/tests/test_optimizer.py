"""Unit tests for the multi-keyword On-Page Optimizer.

Covers keyword normalization on the request and the weighted combined score
(primary keyword counts double each secondary) — no network/DB.
"""

import pytest
from pydantic import ValidationError

from app.schemas.optimizer import (
    AiKeywordSuggestions,
    HeadingCheck,
    ImageCheck,
    KeywordAnalysis,
    KeywordDensityCheck,
    KeywordPlacementCheck,
    LinkCheck,
    MetaDescriptionCheck,
    MetaTitleCheck,
    OnPageChecks,
    OptimizeRequest,
    ReadabilityCheck,
)
from app.services.optimizer_service import _combined_score


def _ka(keyword: str, role: str, score: float) -> KeywordAnalysis:
    checks = OnPageChecks(
        meta_title=MetaTitleCheck(),
        meta_description=MetaDescriptionCheck(),
        headings=HeadingCheck(),
        keyword_placement=KeywordPlacementCheck(),
        keyword_density=KeywordDensityCheck(keyword=keyword),
        links=LinkCheck(),
        images=ImageCheck(),
        readability=ReadabilityCheck(),
    )
    return KeywordAnalysis(
        keyword=keyword,
        role=role,  # type: ignore[arg-type]
        score=score,
        checks=checks,
        ai_suggestions=AiKeywordSuggestions(),
        suggestions=[],
    )


def test_request_normalizes_keywords() -> None:
    req = OptimizeRequest(
        url="example.com",
        keywords=["SEO", " seo ", "", "  ", "tools"],
    )
    # Trimmed, empties dropped, case-insensitive dedupe, order preserved.
    assert req.keywords == ["SEO", "tools"]


def test_request_requires_at_least_one_real_keyword() -> None:
    with pytest.raises(ValidationError):
        OptimizeRequest(url="example.com", keywords=[])
    with pytest.raises(ValidationError):
        OptimizeRequest(url="example.com", keywords=["   ", ""])


def test_combined_score_single_keyword_is_its_own_score() -> None:
    assert _combined_score([_ka("a", "primary", 72.0)]) == 72.0


def test_combined_score_weights_primary_double() -> None:
    items = [_ka("a", "primary", 100.0), _ka("b", "secondary", 40.0)]
    # (100*2 + 40) / 3 == 80.0
    assert _combined_score(items) == 80.0


def test_combined_score_multiple_secondaries() -> None:
    items = [
        _ka("a", "primary", 100.0),
        _ka("b", "secondary", 40.0),
        _ka("c", "secondary", 40.0),
    ]
    # (100*2 + 40 + 40) / 4 == 70.0
    assert _combined_score(items) == 70.0
