"""Build a compact summary of a project's keywords/content.

Shared by the Competitor Intelligence and Content Gap Analysis modules so
they compare against the user's project the same way.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content
from app.models.keyword import Keyword
from app.models.project import Project
from app.schemas.competitor import UserProjectSummary


def _dedupe(values: list[str], limit: int) -> list[str]:
    seen: list[str] = []
    lowered: set[str] = set()
    for value in values:
        value = (value or "").strip()
        if value and value.lower() not in lowered:
            seen.append(value)
            lowered.add(value.lower())
        if len(seen) >= limit:
            break
    return seen


async def build_user_summary(
    db: AsyncSession, project: Project
) -> UserProjectSummary:
    keywords = list(
        (
            await db.execute(
                select(Keyword).where(Keyword.project_id == project.id)
            )
        ).scalars()
    )
    content = list(
        (
            await db.execute(
                select(Content).where(Content.project_id == project.id)
            )
        ).scalars()
    )

    top_keywords = _dedupe([k.term for k in keywords], 40)
    top_topics = _dedupe(
        [k.cluster_label for k in keywords if k.cluster_label]
        + [c.topic for c in content]
        + [c.target_keyword for c in content],
        30,
    )

    return UserProjectSummary(
        project_name=project.name,
        domain=project.domain,
        keyword_count=len(keywords),
        content_count=len(content),
        top_keywords=top_keywords,
        top_topics=top_topics,
    )
