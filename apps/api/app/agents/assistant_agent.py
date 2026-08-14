"""AI SEO Assistant agent (OpenAI Agents SDK) with function-calling tools.

The agent acts as an SEO consultant and answers questions by calling tools
that pull REAL data for the current project from the database: the latest
audit, keyword research, tracked rankings, and content. Every tool is scoped
to the project id carried in the run context, so the assistant can only ever
read the authenticated user's own project data.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from agents import Agent, RunContextWrapper, function_tool
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.audit import AuditReport
from app.models.content import Content
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.rank_tracking import TrackedKeyword


@dataclass
class AssistantContext:
    """Per-run context — scopes every tool to one project."""

    project_id: uuid.UUID


def _pid(ctx: RunContextWrapper[AssistantContext]) -> uuid.UUID:
    return ctx.context.project_id


@function_tool
async def get_project_overview(
    ctx: RunContextWrapper[AssistantContext],
) -> str:
    """Get the project's name, domain, and how much data exists across
    modules (keyword count, content count, tracked keywords, whether an
    audit has been run). Call this first to orient yourself."""
    pid = _pid(ctx)
    async with AsyncSessionLocal() as db:
        project = await db.get(Project, pid)
        if project is None:
            return json.dumps({"error": "project not found"})

        async def count(model) -> int:
            return int(
                (
                    await db.execute(
                        select(func.count()).where(model.project_id == pid)
                    )
                ).scalar_one()
            )

        audit_count = await count(AuditReport)
        return json.dumps(
            {
                "name": project.name,
                "domain": project.domain,
                "keyword_count": await count(Keyword),
                "content_count": await count(Content),
                "tracked_keyword_count": await count(TrackedKeyword),
                "has_audit": audit_count > 0,
            }
        )


@function_tool
async def get_latest_audit(ctx: RunContextWrapper[AssistantContext]) -> str:
    """Get the most recent completed website audit for this project: SEO
    score, issue counts by severity, and the top issues with
    recommendations. Use this for technical/on-page ranking questions."""
    pid = _pid(ctx)
    async with AsyncSessionLocal() as db:
        audit = (
            await db.execute(
                select(AuditReport)
                .where(
                    AuditReport.project_id == pid,
                    AuditReport.status == "completed",
                )
                .order_by(AuditReport.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if audit is None or not audit.results:
        return json.dumps({"audit": None, "note": "No completed audit yet."})

    results = audit.results
    issues = results.get("issues", [])
    severity: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for issue in issues:
        sev = issue.get("severity", "info")
        severity[sev] = severity.get(sev, 0) + 1

    return json.dumps(
        {
            "url": audit.url,
            "score": audit.score,
            "severity_counts": severity,
            "top_issues": [
                {
                    "severity": i.get("severity"),
                    "message": i.get("message"),
                    "recommendation": i.get("recommendation"),
                }
                for i in issues[:8]
            ],
        }
    )


@function_tool
async def get_tracked_rankings(
    ctx: RunContextWrapper[AssistantContext], keyword: str = ""
) -> str:
    """Get SERP rank history for this project's tracked keywords. Optionally
    filter by a `keyword` substring. Returns each keyword's latest position,
    the date it was checked, and the change since tracking began (positive =
    improved / moved up). Use for "why is my page not ranking" questions."""
    pid = _pid(ctx)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(TrackedKeyword)
            .where(TrackedKeyword.project_id == pid)
            .options(selectinload(TrackedKeyword.snapshots))
        )
        if keyword:
            stmt = stmt.where(TrackedKeyword.keyword.ilike(f"%{keyword}%"))
        tracked = list((await db.execute(stmt)).scalars())

    out = []
    for tk in tracked:
        snaps = sorted(tk.snapshots, key=lambda s: s.checked_on)
        latest = snaps[-1] if snaps else None
        earliest = snaps[0] if snaps else None
        change = None
        if (
            latest
            and earliest
            and latest.position is not None
            and earliest.position is not None
        ):
            # Lower position number is better, so improvement = earliest - latest.
            change = earliest.position - latest.position
        out.append(
            {
                "keyword": tk.keyword,
                "latest_position": latest.position if latest else None,
                "checked_on": latest.checked_on.isoformat() if latest else None,
                "change_since_start": change,
                "data_points": len(snaps),
            }
        )
    return json.dumps({"tracked": out} if out else {"tracked": [], "note": "No tracked keywords."})


@function_tool
async def get_keywords(
    ctx: RunContextWrapper[AssistantContext], kind: str = ""
) -> str:
    """Get keyword-research results for this project. Optionally filter by
    `kind` ("related", "long_tail", or "question"). Returns totals by kind
    and a sample of terms with AI-estimated difficulty and search intent."""
    pid = _pid(ctx)
    async with AsyncSessionLocal() as db:
        stmt = select(Keyword).where(Keyword.project_id == pid)
        if kind:
            stmt = stmt.where(Keyword.kind == kind)
        keywords = list((await db.execute(stmt.limit(40))).scalars())
        all_kw = list(
            (
                await db.execute(
                    select(Keyword.kind).where(Keyword.project_id == pid)
                )
            ).scalars()
        )

    by_kind: dict[str, int] = {}
    for k in all_kw:
        by_kind[k] = by_kind.get(k, 0) + 1

    return json.dumps(
        {
            "total": len(all_kw),
            "by_kind": by_kind,
            "sample": [
                {
                    "term": k.term,
                    "kind": k.kind,
                    "difficulty": k.difficulty,
                    "intent": k.search_intent,
                    "cluster": k.cluster_label,
                }
                for k in keywords
            ],
        }
    )


@function_tool
async def get_content(ctx: RunContextWrapper[AssistantContext]) -> str:
    """Get the content pieces created for this project (title, target
    keyword, type, status). Use to see what content already exists when
    advising on content strategy or gaps."""
    pid = _pid(ctx)
    async with AsyncSessionLocal() as db:
        content = list(
            (
                await db.execute(
                    select(Content)
                    .where(Content.project_id == pid)
                    .order_by(Content.created_at.desc())
                    .limit(30)
                )
            ).scalars()
        )
    return json.dumps(
        {
            "count": len(content),
            "pieces": [
                {
                    "title": c.title,
                    "target_keyword": c.target_keyword,
                    "content_type": c.content_type,
                    "status": c.status,
                }
                for c in content
            ],
        }
    )


ASSISTANT_INSTRUCTIONS = """
You are RankPilot AI's SEO Assistant — an expert, practical SEO consultant
embedded in the user's project dashboard.

You have tools that pull REAL data for the current project: project overview,
the latest website audit, tracked keyword rankings (with history), keyword
research, and content pieces. ALWAYS ground your answers in this real data —
call the relevant tools before answering rather than guessing.

How to work:
- For "why is my page not ranking" (or similar), pull the latest audit
  (technical/on-page issues), the tracked rankings (current position + trend),
  and the keywords/content — then explain the likely causes citing the actual
  findings (e.g. the specific audit issues, the current SERP position).
- Be specific and cite the data you pulled (scores, positions, issue names).
- Give prioritized, actionable next steps.
- If a tool returns no data (e.g. no audit yet), say so plainly and suggest
  running that module — never invent numbers.
- Keep answers concise and skimmable (short paragraphs / bullet points).
""".strip()

assistant_agent = Agent[AssistantContext](
    name="SEO Assistant",
    model=settings.OPENAI_MODEL,
    instructions=ASSISTANT_INSTRUCTIONS,
    tools=[
        get_project_overview,
        get_latest_audit,
        get_tracked_rankings,
        get_keywords,
        get_content,
    ],
)
