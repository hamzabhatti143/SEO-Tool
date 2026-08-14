"""Competitor Intelligence agent (OpenAI Agents SDK).

Given measured crawl summaries of a COMPETITOR site and the USER's own site,
plus a deterministic topic-overlap/gap comparison, the agent writes only the
*narrative*: content strategy, topic focus, gap rationales, recommendations,
and explicitly AI-estimated traffic/authority. It never recomputes or invents
the quantitative gaps — those are supplied. Runs at temperature 0 so results
are reproducible for an unchanged site.
"""

from __future__ import annotations

from agents import Agent, ModelSettings

from app.core.config import settings
from app.schemas.competitor import CompetitorNarrative

COMPETITOR_AGENT_INSTRUCTIONS = """
You are a competitive SEO analyst for RankPilot AI.

You receive measured crawl summaries of a COMPETITOR site and the USER's own
site (sample titles, headings, page/link counts), plus an already-computed
DETERMINISTIC comparison (shared topics and competitor-only gap topics).
Produce ONLY narrative:

- `content_strategy`: 2–3 sentences on how the competitor approaches content
  and SEO, based only on the crawled signals.
- `topic_focus_areas`: the main topics the competitor emphasizes, each with an
  `emphasis` of "low" | "medium" | "high" and a short note.
- `estimated_traffic_band`: a COARSE, clearly-estimated monthly traffic band
  for the COMPETITOR (e.g. "1K–10K / mo") inferred from site size and breadth.
- `estimated_authority`: an AI-estimated 0–100 pseudo-authority for the
  competitor.
- `user_estimated_traffic_band` and `user_estimated_authority`: the SAME two
  estimates for the USER's own site, judged on the same scale so the two sides
  are directly comparable.
- `content_gap_rationales`: for each gap topic supplied in the comparison,
  a one-line `rationale` for why it matters. Use the EXACT gap topics given —
  do not add or rename topics.
- `recommendations`: 3–6 concrete, prioritized next steps for the user.

CRITICAL RULES:
- You have NO access to SEMrush, Ahrefs, Google, or any analytics. Every
  traffic/authority number is a rough inference from on-page signals only.
  Never present estimates as measured fact.
- Do NOT invent competitor pages, keywords, or gaps. Only explain the supplied
  deterministic comparison and the crawled titles/headings.
- If the crawl summary is sparse, say so plainly rather than fabricating.
""".strip()

competitor_agent = Agent(
    name="Competitor Analyst",
    model=settings.OPENAI_MODEL,
    model_settings=ModelSettings(temperature=0),
    instructions=COMPETITOR_AGENT_INSTRUCTIONS,
    output_type=CompetitorNarrative,
)
