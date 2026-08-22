"""On-Page SEO Optimizer service.

Crawls a URL (httpx + BeautifulSoup), analyzes it against a target
keyword across meta/heading/placement/density/link/image/readability
dimensions, asks the AI for LSI + missing keywords, and rolls everything
up into a 0–100 score with categorized suggestions.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
import textstat
from agents import Runner
from bs4 import BeautifulSoup

from app.agents.lsi_agent import lsi_agent
from app.core.config import settings
from app.schemas.optimizer import (
    AiKeywordSuggestions,
    AnchorSample,
    HeadingCheck,
    ImageCheck,
    KeywordDensityCheck,
    KeywordPlacementCheck,
    LinkCheck,
    MetaDescriptionCheck,
    MetaTitleCheck,
    OnPageChecks,
    OptimizeRequest,
    OptimizeResponse,
    ReadabilityCheck,
    Suggestion,
)

_USER_AGENT = "RankPilotBot/0.1 (+https://rankpilot.ai/bot)"
_GENERIC_ANCHORS = {
    "click here",
    "here",
    "read more",
    "learn more",
    "more",
    "this",
    "link",
    "this page",
}
_PENALTY = {"critical": 15, "warning": 7, "info": 3}


async def analyze(request: OptimizeRequest) -> OptimizeResponse:
    url = request.url
    if not urlparse(url).scheme:
        url = f"https://{url}"
    keyword = request.target_keyword.strip().lower()

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=settings.AUDIT_REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        final_url = str(response.url)
        soup = BeautifulSoup(response.text, "html.parser")

    visible_text = soup.get_text(separator=" ", strip=True)

    meta_title = _check_meta_title(soup, keyword)
    meta_description = _check_meta_description(soup, keyword)
    headings = _check_headings(soup, keyword)
    first_para = _first_paragraph(soup)
    density = _check_density(visible_text, keyword)
    images = _check_images(soup, keyword)
    links = _check_links(final_url, soup)
    placement = _check_placement(
        meta_title, meta_description, headings, first_para, final_url, images, keyword
    )
    readability = _check_readability(visible_text)

    checks = OnPageChecks(
        meta_title=meta_title,
        meta_description=meta_description,
        headings=headings,
        keyword_placement=placement,
        keyword_density=density,
        links=links,
        images=images,
        readability=readability,
    )

    ai_suggestions = await _ai_keywords(
        request.target_keyword, meta_title, headings, visible_text
    )

    suggestions = _build_suggestions(checks, ai_suggestions)
    score = _score(suggestions)

    return OptimizeResponse(
        url=final_url,
        target_keyword=request.target_keyword,
        score=score,
        checks=checks,
        ai_suggestions=ai_suggestions,
        suggestions=suggestions,
    )


# --- Individual checks ---------------------------------------------------
def _check_meta_title(soup: BeautifulSoup, keyword: str) -> MetaTitleCheck:
    tag = soup.find("title")
    text = tag.get_text(strip=True) if tag else None
    lowered = (text or "").lower()
    return MetaTitleCheck(
        text=text,
        length=len(text) if text else 0,
        has_keyword=keyword in lowered,
        keyword_at_start=lowered.startswith(keyword) if keyword else False,
    )


def _check_meta_description(
    soup: BeautifulSoup, keyword: str
) -> MetaDescriptionCheck:
    tag = soup.find("meta", attrs={"name": "description"})
    text = tag.get("content") if tag else None
    return MetaDescriptionCheck(
        text=text,
        length=len(text) if text else 0,
        has_keyword=keyword in (text or "").lower(),
    )


def _check_headings(soup: BeautifulSoup, keyword: str) -> HeadingCheck:
    counts = {f"h{i}": soup.find_all(f"h{i}") for i in range(1, 7)}
    h1_texts = [h.get_text(strip=True) for h in counts["h1"]]
    subheading_texts = [
        h.get_text(strip=True)
        for level in ("h2", "h3", "h4", "h5", "h6")
        for h in counts[level]
    ]
    return HeadingCheck(
        h1_count=len(counts["h1"]),
        h2_count=len(counts["h2"]),
        h3_count=len(counts["h3"]),
        h4_count=len(counts["h4"]),
        h5_count=len(counts["h5"]),
        h6_count=len(counts["h6"]),
        h1_has_keyword=any(keyword in t.lower() for t in h1_texts),
        subheading_has_keyword=any(
            keyword in t.lower() for t in subheading_texts
        ),
        h1_texts=h1_texts[:10],
    )


def _first_paragraph(soup: BeautifulSoup) -> str:
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 40:
            return text
    return ""


def _check_density(text: str, keyword: str) -> KeywordDensityCheck:
    plain = text.lower()
    words = re.findall(r"\w+", plain)
    word_count = len(words)
    occurrences = len(re.findall(re.escape(keyword), plain)) if keyword else 0
    kw_len = len(keyword.split()) or 1
    density = (
        round(occurrences * kw_len / word_count * 100, 2) if word_count else 0.0
    )
    assessment = (
        "low" if density < 0.5 else "high" if density > 2.5 else "optimal"
    )
    return KeywordDensityCheck(
        keyword=keyword,
        occurrences=occurrences,
        word_count=word_count,
        density_pct=density,
        assessment=assessment,
    )


def _check_images(soup: BeautifulSoup, keyword: str) -> ImageCheck:
    images = soup.find_all("img")
    missing = 0
    with_keyword = 0
    for img in images:
        alt = (img.get("alt") or "").strip()
        if not alt:
            missing += 1
        elif keyword and keyword in alt.lower():
            with_keyword += 1
    return ImageCheck(
        total=len(images), missing_alt=missing, with_keyword_alt=with_keyword
    )


def _anchor_location(anchor) -> str:
    """Describe where an anchor sits: a landmark region or nearest heading."""
    landmarks = {
        "nav": "navigation",
        "header": "header",
        "footer": "footer",
        "aside": "sidebar",
        "main": "main content",
        "article": "article body",
    }
    for parent in anchor.parents:
        name = getattr(parent, "name", None)
        if name in landmarks:
            return landmarks[name]
    heading = anchor.find_previous(["h1", "h2", "h3", "h4"])
    if heading:
        text = heading.get_text(strip=True)
        if text:
            return f'under "{text[:40]}"'
    return "body"


def _check_links(base_url: str, soup: BeautifulSoup) -> LinkCheck:
    base_host = urlparse(base_url).netloc
    internal = 0
    external = 0
    generic = 0
    samples: list[AnchorSample] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        kind = (
            "internal"
            if urlparse(absolute).netloc == base_host
            else "external"
        )
        if kind == "internal":
            internal += 1
        else:
            external += 1

        text = anchor.get_text(strip=True)
        is_generic = (not text) or text.lower() in _GENERIC_ANCHORS
        if is_generic:
            generic += 1
        if len(samples) < 25:
            samples.append(
                AnchorSample(
                    text=text or "(empty)",
                    href=absolute,
                    kind=kind,
                    generic=is_generic,
                    location=_anchor_location(anchor),
                )
            )

    return LinkCheck(
        internal_count=internal,
        external_count=external,
        generic_anchor_count=generic,
        samples=samples,
    )


def _check_placement(
    meta_title: MetaTitleCheck,
    meta_description: MetaDescriptionCheck,
    headings: HeadingCheck,
    first_para: str,
    url: str,
    images: ImageCheck,
    keyword: str,
) -> KeywordPlacementCheck:
    in_url = False
    if keyword:
        slug = urlparse(url).path.lower()
        in_url = keyword.replace(" ", "-") in slug or all(
            tok in slug for tok in keyword.split()
        )

    flags = {
        "in_title": meta_title.has_keyword,
        "in_meta_description": meta_description.has_keyword,
        "in_h1": headings.h1_has_keyword,
        "in_subheadings": headings.subheading_has_keyword,
        "in_first_paragraph": keyword in first_para.lower() if keyword else False,
        "in_url": in_url,
        "in_image_alt": images.with_keyword_alt > 0,
    }
    placement_score = round(sum(flags.values()) / len(flags) * 100, 1)
    return KeywordPlacementCheck(**flags, placement_score=placement_score)


def _check_readability(text: str) -> ReadabilityCheck:
    # textstat needs a meaningful amount of prose to produce a valid score;
    # on empty/tiny pages it returns misleading numbers (or raises). Treat
    # those as "unavailable" rather than reporting a fake 0.0/"difficult".
    if len(re.findall(r"\w+", text)) < 40:
        return ReadabilityCheck(assessment="unavailable")

    try:
        flesch = float(textstat.flesch_reading_ease(text))
        grade = float(textstat.text_standard(text, float_output=True))
    except Exception:  # noqa: BLE001 - textstat can choke on odd inputs
        return ReadabilityCheck(assessment="unavailable")

    if flesch >= 80:
        assessment = "very easy"
    elif flesch >= 70:
        assessment = "easy"
    elif flesch >= 60:
        assessment = "standard"
    elif flesch >= 50:
        assessment = "fairly difficult"
    else:
        assessment = "difficult"

    return ReadabilityCheck(
        flesch_reading_ease=round(flesch, 1),
        grade_level=round(grade, 1),
        assessment=assessment,
    )


# --- AI keyword suggestions ---------------------------------------------
async def _ai_keywords(
    keyword: str,
    meta_title: MetaTitleCheck,
    headings: HeadingCheck,
    visible_text: str,
) -> AiKeywordSuggestions:
    excerpt = visible_text[:1500]
    prompt = (
        f"Target keyword: {keyword}\n"
        f"Page title: {meta_title.text or '(none)'}\n"
        f"H1(s): {', '.join(headings.h1_texts) or '(none)'}\n"
        f"Content excerpt:\n{excerpt}"
    )
    try:
        result = await Runner.run(lsi_agent, prompt)
        return result.final_output  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        return AiKeywordSuggestions(
            lsi_keywords=[],
            missing_keywords=[],
            notes=f"AI keyword suggestions unavailable: {exc}",
        )


# --- Suggestions + score -------------------------------------------------
def _build_suggestions(
    checks: OnPageChecks, ai: AiKeywordSuggestions
) -> list[Suggestion]:
    s: list[Suggestion] = []

    def add(category, severity, message, recommendation):
        s.append(
            Suggestion(
                category=category,
                severity=severity,
                message=message,
                recommendation=recommendation,
            )
        )

    mt = checks.meta_title
    if not mt.text:
        add("meta_title", "critical", "No <title> tag.", "Add a title of 50–60 characters including the keyword.")
    else:
        if not 30 <= mt.length <= 60:
            add("meta_title", "warning", f"Title is {mt.length} characters.", "Aim for 50–60 characters.")
        if not mt.has_keyword:
            add("meta_title", "warning", "Title is missing the target keyword.", "Include the target keyword in the title.")
        elif not mt.keyword_at_start:
            add("meta_title", "info", "Keyword is not near the start of the title.", "Move the keyword toward the front for stronger relevance.")

    md = checks.meta_description
    if not md.text:
        add("meta_description", "warning", "No meta description.", "Add a 140–160 character description including the keyword.")
    else:
        if not 120 <= md.length <= 160:
            add("meta_description", "info", f"Meta description is {md.length} characters.", "Aim for 140–160 characters.")
        if not md.has_keyword:
            add("meta_description", "warning", "Meta description is missing the keyword.", "Work the target keyword into the description naturally.")

    h = checks.headings
    if h.h1_count == 0:
        add("headings", "critical", "No <h1> heading.", "Add exactly one H1 containing the target keyword.")
    elif h.h1_count > 1:
        add("headings", "warning", f"{h.h1_count} <h1> headings found.", "Use a single H1 per page.")
    elif not h.h1_has_keyword:
        add("headings", "warning", "H1 does not contain the keyword.", "Include the target keyword in the H1.")
    if h.h2_count + h.h3_count + h.h4_count + h.h5_count + h.h6_count == 0:
        add("headings", "info", "No H2–H6 subheadings.", "Break the content into sections with subheadings.")

    kp = checks.keyword_placement
    if not kp.in_first_paragraph:
        add("keyword_placement", "warning", "Keyword not found in the first paragraph.", "Mention the keyword within the first 100 words.")
    if not kp.in_url:
        add("keyword_placement", "info", "Keyword not present in the URL slug.", "Include the keyword in the URL where appropriate.")
    if not kp.in_subheadings:
        add("keyword_placement", "info", "Keyword absent from all subheadings.", "Use the keyword or a variation in at least one subheading.")

    kd = checks.keyword_density
    if kd.assessment == "low":
        add("keyword_density", "warning", f"Keyword density is low ({kd.density_pct}%).", "Increase natural usage of the keyword and variants.")
    elif kd.assessment == "high":
        add("keyword_density", "warning", f"Keyword density is high ({kd.density_pct}%).", "Reduce repetition to avoid keyword stuffing.")

    ln = checks.links
    if ln.internal_count == 0:
        add("links", "warning", "No internal links found.", "Add internal links to related pages to aid crawling.")
    if ln.generic_anchor_count > 0:
        add("links", "info", f"{ln.generic_anchor_count} generic anchor texts (e.g. 'click here').", "Use descriptive, keyword-relevant anchor text.")

    im = checks.images
    if im.missing_alt > 0:
        add("images", "warning", f"{im.missing_alt} of {im.total} images missing alt text.", "Add descriptive alt attributes, including the keyword where relevant.")

    rd = checks.readability
    if rd.assessment == "difficult":
        add("readability", "warning", f"Content is hard to read (Flesch {rd.flesch_reading_ease}).", "Shorten sentences and simplify wording.")
    elif rd.assessment == "fairly difficult":
        add("readability", "info", f"Readability is fairly difficult (Flesch {rd.flesch_reading_ease}).", "Consider simplifying some sentences.")

    if ai.missing_keywords:
        add("ai", "info", "The page is missing important related keywords.", "Cover these topics: " + ", ".join(ai.missing_keywords[:8]) + ".")

    return s


def _score(suggestions: list[Suggestion]) -> float:
    score = 100.0
    for item in suggestions:
        score -= _PENALTY.get(item.severity, 5)
    return round(max(score, 0.0), 1)
