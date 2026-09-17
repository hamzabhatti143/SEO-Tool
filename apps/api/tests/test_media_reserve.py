"""Unit tests for carousel/slider/video reserve detection."""

from app.services import media_reserve_service as mr


def test_detects_swiper_with_image_aspect() -> None:
    html = """
    <div class="swiper"><div class="swiper-wrapper">
      <img src="a.jpg" width="1600" height="900">
    </div></div>
    """
    out = mr.detect_reserves(html)
    assert {"selector": ".swiper", "data": {"aspect_ratio": "1600/900"}} in out


def test_video_falls_back_to_16_9() -> None:
    html = '<div class="owl-carousel"><video src="v.mp4"></video></div>'
    out = mr.detect_reserves(html)
    assert {"selector": ".owl-carousel", "data": {"aspect_ratio": "16/9"}} in out


def test_bare_video_with_id_and_dims() -> None:
    html = '<video id="hero-vid" width="1280" height="720" src="v.mp4"></video>'
    out = mr.detect_reserves(html)
    assert {"selector": "#hero-vid", "data": {"aspect_ratio": "1280/720"}} in out


def test_hero_container_css_background_gets_minheight_fallback() -> None:
    # A CSS background-image hero (no <img>/<video>) can't yield an aspect-ratio,
    # so we reserve a conservative viewport-relative min-height instead.
    html = '<div class="header-filter" style="background:url(x.jpg)"></div>'
    out = mr.detect_reserves(html)
    assert {"selector": ".header-filter", "data": {"min_height": "60vh"}} in out


def test_non_hero_container_without_media_is_skipped() -> None:
    # A plain content div (not a recognized carousel/hero) is left alone.
    html = '<div class="content-box"><p>hi</p></div>'
    assert mr.detect_reserves(html) == []


def test_no_media_containers() -> None:
    assert mr.detect_reserves("<div class='content'><p>hi</p></div>") == []


def test_each_selector_emitted_once() -> None:
    html = (
        '<div class="swiper"><img src="a" width="4" height="3"></div>'
        '<div class="swiper"><img src="b" width="16" height="9"></div>'
    )
    out = [o for o in mr.detect_reserves(html) if o["selector"] == ".swiper"]
    assert len(out) == 1  # first match wins, no duplicates
