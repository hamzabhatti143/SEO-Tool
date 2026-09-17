"""Scan stability + range-based comparison for Core Web Vitals.

Lab CWV scores are noisy. A page with a rotating carousel/slider (or any
randomized/rotating media) loads a different frame on each run, so CLS and the
Performance score can swing widely between otherwise-identical loads. Comparing
a single before-scan to a single after-scan then misattributes that natural
variance to the fix — the root cause of "applying a fix worsened the score" and
"reverting worsened it further" reports.

These are pure helpers (no I/O, fully unit-tested):

* ``assess_variance`` — quantify a page's spread and decide ``high_variance``.
* ``compare_ranges`` — a verdict that is only "improved"/"worsened" when the
  before-range and after-range do NOT overlap; otherwise "inconclusive".

Note on PageSpeed caching: within a short window PSI returns a cached run, so
three *consecutive* calls can be identical and under-report variance. The
reliable signal is the spread across *independent* scans over time, so callers
should feed recent history in, not just one scan's internal runs.
"""

from __future__ import annotations

from dataclasses import dataclass


def _spread(values: list[float | None]) -> float:
    present = [float(v) for v in values if v is not None]
    if len(present) < 2:
        return 0.0
    return max(present) - min(present)


@dataclass
class VarianceAssessment:
    high_variance: bool
    score_spread: float
    cls_spread: float
    samples: int


def assess_variance(
    scores: list[float | None],
    cls_values: list[float | None],
    *,
    score_threshold: float = 10.0,
    cls_threshold: float = 0.15,
) -> VarianceAssessment:
    """Flag ``high_variance`` when score spread > threshold OR CLS spread >
    threshold across the supplied runs/history."""
    score_spread = _spread(scores)
    cls_spread = _spread(cls_values)
    samples = max(
        len([s for s in scores if s is not None]),
        len([c for c in cls_values if c is not None]),
    )
    return VarianceAssessment(
        high_variance=(
            score_spread > score_threshold or cls_spread > cls_threshold
        ),
        score_spread=round(score_spread, 3),
        cls_spread=round(cls_spread, 3),
        samples=samples,
    )


Verdict = str  # "improved" | "worsened" | "inconclusive"


@dataclass
class RangeComparison:
    verdict: Verdict
    detail: str


def compare_ranges(
    before: list[float | None],
    after: list[float | None],
    *,
    lower_is_better: bool = False,
) -> RangeComparison:
    """Range-based before/after verdict.

    Only reports "improved"/"worsened" when the two ranges (min–max of each
    set) do NOT overlap. If they overlap, the change is within the page's normal
    variance and we report "inconclusive" instead of a misleading single-number
    delta. ``lower_is_better`` for CLS/LCP; leave False for the score.
    """
    b = [float(x) for x in before if x is not None]
    a = [float(x) for x in after if x is not None]
    if not b or not a:
        return RangeComparison("inconclusive", "insufficient data")

    b_min, b_max = min(b), max(b)
    a_min, a_max = min(a), max(a)

    ranges_overlap = not (a_max < b_min or a_min > b_max)
    span = f"[{b_min:g}–{b_max:g}] → [{a_min:g}–{a_max:g}]"
    if ranges_overlap:
        return RangeComparison(
            "inconclusive",
            f"No conclusive change — within this page's normal variance {span}",
        )

    if lower_is_better:
        improved = a_max < b_min
    else:
        improved = a_min > b_max
    return RangeComparison("improved" if improved else "worsened", span)
