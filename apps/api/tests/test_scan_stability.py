"""Unit tests for scan-stability variance detection + range comparison."""

from app.services import scan_stability as ss


def test_assess_variance_flags_wide_spread() -> None:
    # maptechnologies.co-style history: score 48–94, CLS 0.0–1.345.
    a = ss.assess_variance([48, 62, 71, 94, 58], [0.041, 0.474, 0.76, 1.345, 0.0])
    assert a.high_variance is True
    assert a.score_spread == 46.0
    assert a.cls_spread == 1.345


def test_assess_variance_stable_page() -> None:
    a = ss.assess_variance([90, 92, 91], [0.02, 0.03, 0.02])
    assert a.high_variance is False
    assert a.score_spread == 2.0


def test_assess_variance_thresholds_boundary() -> None:
    # Exactly at threshold is NOT high (uses strict >).
    assert ss.assess_variance([80, 90], [0.0, 0.0]).high_variance is False
    assert ss.assess_variance([80, 91], [0.0, 0.0]).high_variance is True
    assert ss.assess_variance([80, 80], [0.1, 0.25]).high_variance is False
    assert ss.assess_variance([80, 80], [0.1, 0.26]).high_variance is True


def test_assess_variance_ignores_none_and_single() -> None:
    a = ss.assess_variance([None, 70, None], [None])
    assert a.score_spread == 0.0  # only one real value → no spread
    assert a.high_variance is False


def test_compare_ranges_overlap_is_inconclusive() -> None:
    # before 60–68, after 62–65 overlap → inconclusive (natural variance).
    r = ss.compare_ranges([60, 68, 64], [62, 65, 63])
    assert r.verdict == "inconclusive"
    assert "normal variance" in r.detail


def test_compare_ranges_score_improved_when_disjoint() -> None:
    # score higher-is-better; after (85–90) strictly above before (60–68).
    r = ss.compare_ranges([60, 68], [85, 90])
    assert r.verdict == "improved"


def test_compare_ranges_score_worsened_when_disjoint() -> None:
    r = ss.compare_ranges([80, 85], [60, 70])
    assert r.verdict == "worsened"


def test_compare_ranges_cls_lower_is_better() -> None:
    # CLS lower-is-better; after (0.02–0.05) strictly below before (0.4–0.5).
    r = ss.compare_ranges([0.4, 0.5], [0.02, 0.05], lower_is_better=True)
    assert r.verdict == "improved"
    # and the reverse worsens
    r2 = ss.compare_ranges([0.02, 0.05], [0.4, 0.5], lower_is_better=True)
    assert r2.verdict == "worsened"


def test_compare_ranges_insufficient_data() -> None:
    assert ss.compare_ranges([], [70]).verdict == "inconclusive"
