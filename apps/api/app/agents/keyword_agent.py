"""Keyword Research agent (OpenAI Agents SDK).

Given a seed keyword, the agent returns three categories of suggestions —
related keywords, long-tail variations, and People-Also-Ask style
questions — each with an estimated difficulty and search intent, as
structured (typed) output.
"""

from __future__ import annotations

from agents import Agent

from app.core.config import settings
from app.schemas.keyword import (
    N_LONG_TAIL,
    N_QUESTIONS,
    N_RELATED,
    KeywordAgentOutput,
)

KEYWORD_AGENT_INSTRUCTIONS = f"""
You are an expert SEO keyword researcher for RankPilot AI.

Given a single seed keyword, produce THREE categories of suggestions:

1. `related`: exactly {N_RELATED} closely-related head/mid-tail keywords.
2. `long_tail`: exactly {N_LONG_TAIL} specific long-tail variations
   (typically 4+ words) that capture niche intent.
3. `questions`: exactly {N_QUESTIONS} question-based keywords in the style
   of Google's "People Also Ask" (who/what/why/how/is/can ...).

For EVERY keyword in every category, estimate:
- `difficulty`: how hard it is to rank for — one of "low", "medium",
  "high" (lowercase).
- `search_intent`: one of "informational", "commercial",
  "transactional" (lowercase).

Rules:
- Return the exact counts requested for each category.
- All terms must be lowercase and free of surrounding quotes.
- Do NOT repeat the seed keyword verbatim and avoid duplicates.
- Do NOT invent numeric search volumes.
- Every term must be genuinely useful for content and SEO targeting.
""".strip()

keyword_agent = Agent(
    name="Keyword Researcher",
    model=settings.OPENAI_MODEL,
    instructions=KEYWORD_AGENT_INSTRUCTIONS,
    output_type=KeywordAgentOutput,
)
