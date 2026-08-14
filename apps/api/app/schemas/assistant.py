"""Pydantic schemas for the AI SEO Assistant module."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    project_id: uuid.UUID
    # Full conversation so far (last item is the new user message).
    messages: list[ChatMessage] = Field(..., min_length=1)
