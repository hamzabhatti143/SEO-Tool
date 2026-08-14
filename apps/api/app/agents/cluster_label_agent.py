"""Cluster labeling agent (OpenAI Agents SDK).

Given several clusters of keywords, produce a concise topic label for
each. Used to name the keyword clusters shown in the UI.
"""

from __future__ import annotations

from agents import Agent
from pydantic import BaseModel

from app.core.config import settings


class ClusterLabels(BaseModel):
    """One label per cluster, in the same order as the input clusters."""

    labels: list[str]


CLUSTER_LABEL_INSTRUCTIONS = """
You are an SEO topic strategist. You are given several numbered clusters of
keywords. For EACH cluster, return one concise topic label (2–4 words,
Title Case) that captures the shared theme.

Rules:
- Return exactly one label per cluster, in the same order as the input.
- Labels must be short, human-readable topic names — not full sentences.
- Do not number the labels.
""".strip()

cluster_label_agent = Agent(
    name="Cluster Labeler",
    model=settings.OPENAI_MODEL,
    instructions=CLUSTER_LABEL_INSTRUCTIONS,
    output_type=ClusterLabels,
)
