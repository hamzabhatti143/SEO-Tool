"""On-Page LSI/NLP keyword agent (OpenAI Agents SDK).

Given a target keyword and a summary of what is already on the page, the
agent proposes semantically-related (LSI/NLP) keywords and important
"missing" keywords the page should cover — as structured output.
"""

from __future__ import annotations

from agents import Agent

from app.core.config import settings
from app.schemas.optimizer import AiKeywordSuggestions

LSI_AGENT_INSTRUCTIONS = """
You are an on-page SEO and NLP specialist for RankPilot AI.

You are given a target keyword and a summary of a web page's current
content (title, headings, and an excerpt). Produce:

- `lsi_keywords`: 10–15 semantically related (LSI/NLP) terms and entities
  that strengthen topical relevance for the target keyword.
- `missing_keywords`: 5–10 important subtopics or keywords that the page
  does NOT currently cover but should, to fully satisfy search intent.
- `notes`: one or two sentences of concrete on-page guidance.

Rules:
- All keywords lowercase, no surrounding quotes, no duplicates.
- Do NOT repeat the exact target keyword.
- `missing_keywords` must be genuinely absent from the provided content.
- Do NOT invent search volumes or metrics.
""".strip()

lsi_agent = Agent(
    name="LSI Keyword Analyst",
    model=settings.OPENAI_MODEL,
    instructions=LSI_AGENT_INSTRUCTIONS,
    output_type=AiKeywordSuggestions,
)
