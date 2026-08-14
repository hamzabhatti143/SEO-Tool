"""Deterministic topic extraction and gap comparison.

Given two crawled site profiles, extract each site's dominant topics from its
page titles + headings and compute overlap/gaps in pure Python — no LLM. This
keeps the quantitative comparison reproducible for unchanged sites and stops
the model from inventing keywords or pages that were never crawled.

Quality guards: page text is de-glued (nested-tag headings get spaces),
CMS/archive boilerplate is dropped, and each site's own brand name (derived
from its domain) is excluded so gaps are real topics, not brand mentions.
"""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlparse

from app.schemas.competitor import CompetitorProfile, Comparison

# Common English + web/CMS boilerplate stopwords to drop from topics.
_STOPWORDS = frozenset(
    """
    a an and are as at be but by for from has have how in into is it its of on
    or that the their they this to was were what when where which who will with
    your you our we us do does can yours home page pages about contact privacy
    terms blog post posts read more menu search login sign register get best
    top new free guide guides vs welcome hello click here view learn find
    archive archives archived category categories tag tags tagged author authors
    admin comment comments reply uncategorized posted date recent related next
    previous prev continue reading share copyright rights reserved all site
    website services service company agency online near me
    """.split()
)

# Titles/headings from CMS archive, tag, author and pagination pages carry no
# topical signal — skip whole lines that look like them.
_ARCHIVE_RE = re.compile(
    r"\b(category|tag|author|monthly|yearly|daily)\s+archives?\b"
    r"|^\s*archives?\b|\bpage\s+\d+\b|\bpage\s+\d+\s+of\s+\d+\b",
    re.IGNORECASE,
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'&-]*")
_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _domain_label(profile: CompetitorProfile) -> str:
    """Second-level domain label, e.g. www.oscarghostwriting.com -> oscarghostwriting."""
    host = urlparse(profile.url).netloc or profile.domain
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    return parts[0].lower() if parts else host.lower()


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 2 and t not in _STOPWORDS and not t.isdigit()
    ]


def _corpus(profile: CompetitorProfile) -> list[str]:
    # Use each crawled page's title + h1 (top_headings is a redundant subset of
    # the h1s and would double-count boilerplate hero headings).
    lines: list[str] = []
    for page in profile.pages:
        for value in (page.title, page.h1):
            if value:
                clean = _clean(value)
                if clean and not _ARCHIVE_RE.search(clean):
                    lines.append(clean)
    if not lines:  # fallback for callers with no page bodies
        lines = [
            _clean(h)
            for h in profile.sample_titles + profile.top_headings
            if h and not _ARCHIVE_RE.search(_clean(h))
        ]
    return lines


def _scored(profile: CompetitorProfile) -> dict[str, int]:
    """Score unigrams + bigrams by frequency (phrases weighted higher)."""
    unigrams: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    for line in _corpus(profile):
        toks = _tokens(line)
        unigrams.update(toks)
        for a, b in zip(toks, toks[1:]):
            bigrams[f"{a} {b}"] += 1

    scored: dict[str, int] = {}
    for term, n in bigrams.items():
        if n >= 2:
            scored[term] = n * 2  # prefer specific multi-word topics
    for term, n in unigrams.items():
        if n >= 2:
            scored.setdefault(term, n)
    return scored


def _brand_tokens(
    scored: dict[str, int], label: str, shared_singles: set[str]
) -> set[str]:
    """Single-word topics that are part of the site's own domain brand (and not
    a topic shared with the other site, so real industry terms are kept)."""
    brand = {label}
    for term in scored:
        if " " in term:
            continue
        if len(term) >= 3 and term in label and term not in shared_singles:
            brand.add(term)
    return brand


def _finalize(
    scored: dict[str, int], brand: set[str], limit: int
) -> list[str]:
    out: list[str] = []
    for term, _ in sorted(scored.items(), key=lambda kv: (-kv[1], kv[0])):
        words = term.split()
        if any(w in brand for w in words) or term in brand:
            continue
        out.append(term)
        if len(out) >= limit:
            break
    return out


def extract_topics(profile: CompetitorProfile, limit: int = 25) -> list[str]:
    """Public helper: frequency-ranked topics with brand/boilerplate removed."""
    scored = _scored(profile)
    brand = _brand_tokens(scored, _domain_label(profile), set())
    return _finalize(scored, brand, limit)


def _covers(topic: str, own: set[str]) -> bool:
    """A topic is 'covered' if it matches, or its words are subsumed by, the
    other site's topics — so "book writing" counts as covered by "book"/"writing"."""
    if topic in own:
        return True
    words = topic.split()
    if len(words) > 1 and all(w in own for w in words):
        return True
    return any(topic in t or t in topic for t in own)


def compare(
    user: CompetitorProfile, competitor: CompetitorProfile
) -> Comparison:
    """Compute shared topics and gaps deterministically from both crawls."""
    user_scored = _scored(user)
    comp_scored = _scored(competitor)

    user_singles = {t for t in user_scored if " " not in t}
    comp_singles = {t for t in comp_scored if " " not in t}
    shared_singles = user_singles & comp_singles

    user_label = _domain_label(user)
    comp_label = _domain_label(competitor)
    brand = (
        _brand_tokens(user_scored, user_label, shared_singles)
        | _brand_tokens(comp_scored, comp_label, shared_singles)
    )

    user_topics = _finalize(user_scored, brand, 25)
    competitor_topics = _finalize(comp_scored, brand, 25)
    user_set = set(user_topics)
    competitor_set = set(competitor_topics)

    shared = [t for t in competitor_topics if _covers(t, user_set)]
    keyword_gaps = [t for t in competitor_topics if not _covers(t, user_set)]
    user_advantages = [t for t in user_topics if not _covers(t, competitor_set)]

    return Comparison(
        user_topics=user_topics,
        competitor_topics=competitor_topics,
        shared_topics=shared[:20],
        keyword_gaps=keyword_gaps[:20],
        user_advantages=user_advantages[:20],
    )
