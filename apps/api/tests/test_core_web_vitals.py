"""Unit tests for the PageSpeed Insights parsing/report engine.

These exercise ``_build_report`` with synthetic PSI responses, so no network
or API key is needed.
"""

from app.services.core_web_vitals_service import _build_report, _field_inp


def _audit(title, *, score=None, numeric=None, sdm="numeric", details=None,
           display_value=None):
    a = {"title": title, "score": score, "scoreDisplayMode": sdm}
    if numeric is not None:
        a["numericValue"] = numeric
    if details is not None:
        a["details"] = details
    if display_value is not None:
        a["displayValue"] = display_value
    return a


def _psi(*, scores, audits, refs, loading_experience=None):
    """Build a minimal PSI v5 response."""
    categories = {}
    for key, score in scores.items():
        categories[key] = {"score": score, "auditRefs": refs.get(key, [])}
    data = {
        "lighthouseResult": {
            "lighthouseVersion": "12.0.0",
            "fetchTime": "2026-08-22T12:00:00.000Z",
            "requestedUrl": "https://example.com/",
            "finalDisplayedUrl": "https://example.com/",
            "configSettings": {
                "formFactor": "mobile",
                "throttlingMethod": "simulate",
            },
            "categories": categories,
            "audits": audits,
        }
    }
    if loading_experience is not None:
        data["loadingExperience"] = loading_experience
    return data


_AUDITS = {
    "first-contentful-paint": _audit("FCP", numeric=1800),
    "largest-contentful-paint": _audit("LCP", numeric=3000),
    "total-blocking-time": _audit("TBT", numeric=450),
    "cumulative-layout-shift": _audit("CLS", numeric=0.08),
    "speed-index": _audit("Speed Index", numeric=4200),
    "render-blocking-resources": _audit(
        "Eliminate render-blocking resources",
        score=0.5,
        sdm="metricSavings",
        details={"type": "opportunity", "overallSavingsMs": 700},
        display_value="Est savings of 700 ms",
    ),
    "uses-long-cache-ttl": _audit(
        "Serve static assets with an efficient cache policy",
        score=0.3,
        sdm="informative",
    ),
    "non-composited-animations": _audit(
        "Avoid non-composited animations", score=None, sdm="informative"
    ),
    "uses-http2": _audit("Use HTTP/2", score=1, sdm="binary"),
    "viewport": _audit("Has a viewport meta tag", score=1, sdm="binary"),
    "screenshot-thumbnails": {
        "title": "Screenshot Thumbnails",
        "scoreDisplayMode": "informative",
        "details": {"items": [{"data": "data:image/jpeg;base64,AAA"},
                               {"data": "data:image/jpeg;base64,BBB"}]},
    },
    "final-screenshot": {
        "title": "Final Screenshot",
        "scoreDisplayMode": "informative",
        "details": {"data": "data:image/jpeg;base64,FINAL"},
    },
}

_REFS = {
    "performance": [
        {"id": "first-contentful-paint"},
        {"id": "largest-contentful-paint"},
        {"id": "render-blocking-resources"},
        {"id": "uses-long-cache-ttl"},
        {"id": "non-composited-animations"},
        {"id": "uses-http2"},
    ],
    "accessibility": [{"id": "viewport"}],
    "best_practices": [],
    "seo": [],
}


def _response(**overrides):
    return _psi(
        scores={
            "performance": 0.72,
            "accessibility": 0.95,
            "best-practices": 1.0,
            "seo": 0.9,
        },
        audits=_AUDITS,
        refs={
            "performance": _REFS["performance"],
            "accessibility": _REFS["accessibility"],
            "best-practices": [],
            "seo": [],
        },
        **overrides,
    )


def test_lab_metrics_extracted() -> None:
    report = _build_report([_response()], "mobile")
    assert report.metrics.fcp == 1800
    assert report.metrics.lcp == 3000
    assert report.metrics.tbt == 450
    assert report.metrics.cls == 0.08
    assert report.metrics.speed_index == 4200


def test_category_scores_all_four() -> None:
    report = _build_report([_response()], "mobile")
    assert report.categories["performance"].score == 72
    assert report.categories["accessibility"].score == 95
    assert report.categories["best_practices"].score == 100
    assert report.categories["seo"].score == 90


def test_no_field_inp_is_none_not_zero() -> None:
    report = _build_report([_response()], "mobile")
    assert report.field_inp is None  # never a fake 0


def test_field_inp_from_loading_experience() -> None:
    le = {"metrics": {"INTERACTION_TO_NEXT_PAINT": {"percentile": 210}}}
    report = _build_report([_response(loading_experience=le)], "mobile")
    assert report.field_inp == 210
    assert _field_inp(le) == 210
    assert _field_inp({"metrics": {}}) is None


def test_audit_classification() -> None:
    perf = _build_report([_response()], "mobile").categories["performance"]
    # Opportunity with savings → insight (metric audits excluded).
    assert [a.id for a in perf.insights] == ["render-blocking-resources"]
    assert perf.insights[0].savings_ms == 700
    # Failing informational + null-informative → diagnostics.
    diag_ids = {a.id for a in perf.diagnostics}
    assert diag_ids == {"uses-long-cache-ttl", "non-composited-animations"}
    # score == 1 → passed.
    assert perf.passed_count == 1
    assert perf.passed_titles == ["Use HTTP/2"]


def test_screenshots_and_metadata() -> None:
    report = _build_report([_response()], "mobile")
    assert len(report.screenshots.timeline) == 2
    assert report.screenshots.final == "data:image/jpeg;base64,FINAL"
    assert report.metadata.lighthouse_version == "12.0.0"
    assert report.metadata.form_factor == "mobile"
    assert report.metadata.throttling_method == "simulate"


def test_median_across_two_runs() -> None:
    run_a = _response()
    run_b = _response()
    # Second run: slower LCP so the median differs from either single run.
    run_b["lighthouseResult"]["audits"] = {
        **_AUDITS,
        "largest-contentful-paint": _audit("LCP", numeric=5000),
    }
    report = _build_report([run_a, run_b], "mobile")
    assert report.metrics.lcp == 4000  # median([3000, 5000])
    assert len(report.runs) == 2
    assert {r.lcp for r in report.runs} == {3000, 5000}
