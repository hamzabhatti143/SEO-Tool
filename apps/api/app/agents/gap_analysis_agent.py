"""Content Gap Analysis agent (OpenAI Agents SDK).

Cross-references what 2–3 competitors cover against the user's project and
produces missing topics, missing FAQs, and a ready-to-use content brief for
each opportunity — as structured output.
"""

from __future__ import annotations

from agents import Agent

from app.core.config import settings
from app.schemas.gap_analysis import GapAnalysisOutput

GAP_AGENT_INSTRUCTIONS = """
You are a content strategist for RankPilot AI.

You receive a summary of the USER's project (domain, keywords, topics) and
crawl summaries for 2–3 COMPETITORS (page titles and headings). Cross-
reference them and produce:

- `missing_topics`: topics/themes that MULTIPLE competitors cover but the
  user's project does not. Prioritize topics covered by more than one
  competitor. Lowercase, de-duplicated.
- `missing_faqs`: People-Also-Ask style questions users likely search for
  in this space that the user's project does not appear to answer.
- `content_briefs`: for the highest-value gaps, a concrete brief with:
    - `title`: a compelling, SEO-friendly article/page title.
    - `target_keyword`: the primary keyword to target (lowercase).
    - `content_type`: "blog" | "product_description" | "landing_page".
    - `outline`: 4–7 section headings.
    - `word_count_target`: a realistic integer (e.g. 800–2000).
    - `priority`: "high" | "medium" | "low" (high = clear multi-competitor
      gap with strong intent).
    - `rationale`: one line on why this gap matters.

Rules:
- Base everything on the ACTUAL competitor titles/headings provided and the
  user's stated coverage — do not invent competitor pages.
- Generate 5–10 briefs, ordered from highest to lowest priority.
""".strip()

gap_analysis_agent = Agent(
    name="Content Gap Strategist",
    model=settings.OPENAI_MODEL,
    instructions=GAP_AGENT_INSTRUCTIONS,
    output_type=GapAnalysisOutput,
)
