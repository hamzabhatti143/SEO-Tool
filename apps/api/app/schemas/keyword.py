"""Pydantic schemas for the Keyword Research module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# related terms, long-tail variations, and People-Also-Ask style questions.
KeywordKind = Literal["related", "long_tail", "question"]
SearchIntent = Literal["informational", "commercial", "transactional"]
Difficulty = Literal["low", "medium", "high"]

# Target counts per category.
N_RELATED = 20
N_LONG_TAIL = 10
N_QUESTIONS = 10


class KeywordResearchRequest(BaseModel):
    project_id: uuid.UUID
    seed_keyword: str = Field(..., min_length=1, max_length=255)


class KeywordItem(BaseModel):
    """A single keyword suggestion with AI-estimated attributes."""

    term: str
    difficulty: Difficulty
    search_intent: SearchIntent

    @field_validator("difficulty", "search_intent", mode="before")
    @classmethod
    def _lowercase(cls, v: object) -> object:
        # Be forgiving if the model returns e.g. "Low" or "Commercial".
        return v.lower() if isinstance(v, str) else v


class KeywordAgentOutput(BaseModel):
    """Structured output the OpenAI agent is asked to return.

    The agent returns each category as its own list so the target counts
    (20 / 10 / 5) can be requested and validated explicitly.
    """

    seed_keyword: str
    related: list[KeywordItem]
    long_tail: list[KeywordItem]
    questions: list[KeywordItem]


class KeywordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    seed_keyword: str
    term: str
    kind: str
    search_intent: str | None = None
    difficulty: str | None = None
    search_volume: int | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None
    trend_score: int | None = None
    trend_direction: str | None = None
    created_at: datetime
