"""Google Trends (pytrends) integration — a free alternative to paid
search-volume data.

pytrends is synchronous (requests-based) and heavily rate-limited by
Google, so this is intentionally best-effort: call ``fetch_trends`` via
``asyncio.to_thread`` and treat any missing entry as "no data". It never
raises — throttling simply yields fewer results.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from app.core.config import settings


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def fetch_trends(terms: list[str]) -> dict[str, dict]:
    """Return ``{term: {"score": int, "direction": str}}`` (best-effort).

    ``score`` is the recent average interest (0–100). ``direction`` compares
    the first vs. second half of the last 12 months: rising | falling | flat.
    """
    from pytrends.request import TrendReq  # local import: heavy optional dep

    results: dict[str, dict] = {}
    capped = terms[: settings.KEYWORD_TREND_MAX_TERMS]
    if not capped:
        return results

    try:
        pytrends = TrendReq(hl="en-US", tz=0)
    except Exception:  # noqa: BLE001 - network/init failure: degrade
        return results

    # Google Trends accepts at most 5 terms per interest_over_time payload.
    for batch in _chunks(capped, 5):
        try:
            pytrends.build_payload(batch, timeframe="today 12-m")
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                continue
            for term in batch:
                if term not in df.columns:
                    continue
                series = df[term]
                if series.empty:
                    continue
                half = max(len(series) // 2, 1)
                first = float(series.iloc[:half].mean())
                second = float(series.iloc[half:].mean())
                if second > first * 1.1:
                    direction = "rising"
                elif second < first * 0.9:
                    direction = "falling"
                else:
                    direction = "flat"
                results[term] = {
                    "score": int(round(float(series.tail(4).mean()))),
                    "direction": direction,
                }
        except Exception:  # noqa: BLE001 - throttled/blocked: skip this batch
            continue
        time.sleep(settings.KEYWORD_TREND_SLEEP)

    return results
