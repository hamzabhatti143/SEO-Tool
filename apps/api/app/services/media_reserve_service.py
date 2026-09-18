"""Detect carousel/slider/video containers that need size reservation (CLS).

Rotating media (Slick / Swiper / Owl carousels, `<video>`, theme hero sliders)
shifts layout because each frame has a different intrinsic size — compressing
the media does NOT stabilise it. The only fix is to reserve the container's
size up front. This module finds those containers in a page and emits
``reserve_media_dimensions`` instructions (a CSS selector + an aspect-ratio or
min-height) that the plugin injects via wp_head.

``detect_reserves(html)`` is a pure function (unit-tested); the async
``fetch_and_detect`` wraps it with an HTTP GET.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

# Container class fragments → the CSS selector we reserve. Ordered; first match
# on an element wins. Kept conservative: only well-known rotating-media widgets.
_CAROUSEL_CLASSES: dict[str, str] = {
    "swiper": ".swiper",
    "slick-slider": ".slick-slider",
    "owl-carousel": ".owl-carousel",
    "wp-block-cover__video-background": ".wp-block-cover",
    # Common theme hero/slider hooks (Hestia + generic).
    "header-filter": ".header-filter",
    "carousel-inner": ".carousel-inner",
    "carousel": ".carousel",
}

# Full-height hero containers whose media is a CSS background-image (no
# measurable <img>/<video>). No aspect-ratio can be derived, so we reserve a
# viewport-relative min-height instead. This is a conservative estimate — it
# prevents the bulk of the shift and is fully revertible; the exact value can
# be tuned in the Customizer if the hero is shorter/taller than a typical hero.
_HERO_FALLBACK_CLASSES = frozenset(
    {"header-filter", "carousel-inner", "carousel"}
)
# Reserve close to a full-screen hero's real height (measured ~90vh on the
# themes we've profiled). 85vh covers the bulk of the shift with a small safety
# margin against over-reserving; revertible + tunable in the Customizer.
_HERO_FALLBACK_MIN_HEIGHT = "85vh"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _aspect_from_dims(w: str | None, h: str | None) -> str | None:
    try:
        wi, hi = int(float(w)), int(float(h))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if wi <= 0 or hi <= 0:
        return None
    return f"{wi}/{hi}"


def detect_reserves(html: str) -> list[dict[str, Any]]:
    """Return reserve instructions for rotating-media containers in ``html``.

    Each item is ``{"selector": ".swiper", "data": {"aspect_ratio": "16/9"}}``
    (or ``{"min_height": "..."}``). Aspect-ratio is derived from an inner
    img/video's width/height when available (the safe, responsive reservation);
    a ``<video>`` with no dimensions falls back to 16/9; a hero-style container
    with no measurable media is skipped (no safe generic value) rather than
    guessing — the plugin/UI then reports it as not auto-reservable.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def emit(selector: str, data: dict[str, str]) -> None:
        if selector in seen or not data:
            return
        seen.add(selector)
        out.append({"selector": selector, "data": data})

    # Carousels/sliders by container class.
    for el in soup.find_all(True):
        classes = " ".join(el.get("class", []))
        if not classes:
            continue
        for fragment, selector in _CAROUSEL_CLASSES.items():
            if fragment not in classes or selector in seen:
                continue
            media = el.find(["img", "video"])
            aspect = None
            if media is not None:
                aspect = _aspect_from_dims(media.get("width"), media.get("height"))
            if aspect:
                emit(selector, {"aspect_ratio": aspect})
            elif media is not None and media.name == "video":
                emit(selector, {"aspect_ratio": "16/9"})
            elif fragment in _HERO_FALLBACK_CLASSES:
                # CSS-background hero (no measurable media) → reserve height.
                emit(selector, {"min_height": _HERO_FALLBACK_MIN_HEIGHT})
            # else: not a recognized hero → skip (don't guess).

    # Bare <video> elements with intrinsic size.
    for v in soup.find_all("video"):
        aspect = _aspect_from_dims(v.get("width"), v.get("height")) or "16/9"
        vid = v.get("id")
        if vid and re.match(r"^[A-Za-z][\w-]*$", vid):
            emit(f"#{vid}", {"aspect_ratio": aspect})

    # Overlap neutraliser: some themes (e.g. Hestia) pull the main content up
    # over the hero with a negative margin — when the hero's height resolves,
    # that content JUMPS. If we reserved a hero AND a `.main-raised` overlap
    # exists, zero its top margin so it no longer depends on the hero height.
    reserved_hero = any(o["selector"] in _HERO_SELECTORS for o in out)
    if reserved_hero and soup.select_one(".main-raised"):
        emit(".main.main-raised", {"margin_top": "0"})

    return out


_HERO_SELECTORS = frozenset({".header-filter", ".carousel", ".carousel-inner"})


async def fetch_and_detect(url: str) -> list[dict[str, Any]]:
    """Fetch ``url`` and detect reservable media containers. Best-effort: an
    unreachable page yields no instructions rather than raising."""
    if "://" not in url:
        url = f"https://{url}"
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            timeout=settings.AUDIT_REQUEST_TIMEOUT,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
        if resp.status_code != 200 or "<" not in resp.text:
            return []
        return detect_reserves(resp.text)
    except httpx.HTTPError:
        return []
