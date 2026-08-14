"""Content Gap Analysis service.

Crawls 2–3 competitors (reusing the competitor crawler), then asks the AI
to cross-reference their coverage against the user's project and emit
missing topics, missing FAQs, and actionable content briefs.
"""

from __future__ import annotations

import asyncio

from agents import Runner

from app.agents.gap_analysis_agent import gap_analysis_agent
from app.core.config import settings
from app.schemas.competitor import CompetitorProfile, UserProjectSummary
from app.schemas.gap_analysis import (
    CompetitorSummary,
    GapAnalysisOutput,
    GapAnalysisResponse,
)
from app.services import competitor_service


async def analyze(
    competitor_urls: list[str], user_summary: UserProjectSummary
) -> GapAnalysisResponse:
    # Crawl the competitors concurrently (each is internally bounded).
    results = await asyncio.gather(
        *(
            competitor_service.crawl_site(
                url, max_pages=settings.GAP_MAX_PAGES_PER_COMPETITOR
            )
            for url in competitor_urls[:3]
        ),
        return_exceptions=True,
    )
    profiles = [
        r
        for r in results
        if isinstance(r, CompetitorProfile) and r.crawl_status.ok
    ]
    if not profiles:
        raise RuntimeError("Could not crawl any of the provided competitors.")

    output = await _analyze_with_ai(profiles, user_summary)

    return GapAnalysisResponse(
        user_project=user_summary,
        competitors=[
            CompetitorSummary(
                url=p.url,
                domain=p.domain,
                pages_crawled=p.structure.pages_crawled,
                sample_titles=p.sample_titles,
            )
            for p in profiles
        ],
        missing_topics=output.missing_topics,
        missing_faqs=output.missing_faqs,
        content_briefs=output.content_briefs,
    )


async def _analyze_with_ai(
    profiles: list[CompetitorProfile], user: UserProjectSummary
) -> GapAnalysisOutput:
    competitor_blocks = []
    for p in profiles:
        titles = "\n".join(f"  - {t}" for t in p.sample_titles)
        headings = "\n".join(f"  - {h}" for h in p.top_headings)
        competitor_blocks.append(
            f"COMPETITOR: {p.domain} ({p.structure.pages_crawled} pages)\n"
            f" Titles:\n{titles}\n Headings:\n{headings}"
        )

    prompt = (
        "USER PROJECT\n"
        f"Domain: {user.domain}\n"
        f"Keywords ({user.keyword_count}): {', '.join(user.top_keywords)}\n"
        f"Topics ({user.content_count} pieces): {', '.join(user.top_topics)}\n\n"
        + "\n\n".join(competitor_blocks)
        + "\n\nIdentify what the competitors cover that the user does not, "
        "and produce content briefs for the best opportunities."
    )
    result = await Runner.run(gap_analysis_agent, prompt)
    return result.final_output  # type: ignore[return-value]
