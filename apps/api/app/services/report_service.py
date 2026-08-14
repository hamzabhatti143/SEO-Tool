"""Reports service.

Aggregates Audit + Keyword Research + Content data for a project into a
single branded report, rendered as HTML (Jinja2) and optionally PDF
(WeasyPrint). Agency-plan users get white-label branding (their logo/name/
color from project settings) instead of RankPilot AI branding.

NOTE: PDF output uses WeasyPrint, which needs native libraries (Pango,
cairo, GDK-PixBuf / GTK on Windows). If those aren't installed, the HTML
report still works — the PDF endpoint returns a clear 503.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import date

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditReport
from app.models.content import Content
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.user import User


@dataclass
class Branding:
    name: str
    logo_url: str | None
    color: str
    white_label: bool


def _resolve_branding(project: Project, user: User) -> Branding:
    """Agency users with configured branding get white-label; else RankPilot."""
    if user.plan == "agency" and project.brand_name:
        return Branding(
            name=project.brand_name,
            logo_url=project.brand_logo_url,
            color=project.brand_color or "#111827",
            white_label=True,
        )
    return Branding(
        name="RankPilot AI", logo_url=None, color="#2563eb", white_label=False
    )


async def _gather_context(
    db: AsyncSession, project: Project, user: User
) -> dict:
    # Latest completed audit.
    audit = (
        await db.execute(
            select(AuditReport)
            .where(
                AuditReport.project_id == project.id,
                AuditReport.status == "completed",
            )
            .order_by(AuditReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    audit_ctx = None
    if audit and audit.results:
        results = audit.results
        issues = results.get("issues", [])
        severity = Counter(i.get("severity", "info") for i in issues)
        audit_ctx = {
            "score": audit.score,
            "url": audit.url,
            "checked_on": audit.completed_at,
            "critical": severity.get("critical", 0),
            "warning": severity.get("warning", 0),
            "info": severity.get("info", 0),
            "issues": issues[:15],
            "meta": results.get("meta", {}),
        }

    keywords = list(
        (
            await db.execute(
                select(Keyword).where(Keyword.project_id == project.id)
            )
        ).scalars()
    )
    kind_counts = Counter(k.kind for k in keywords)
    clusters = sorted({k.cluster_label for k in keywords if k.cluster_label})
    keyword_ctx = {
        "total": len(keywords),
        "related": kind_counts.get("related", 0),
        "long_tail": kind_counts.get("long_tail", 0),
        "question": kind_counts.get("question", 0),
        "clusters": clusters,
        "sample": keywords[:25],
    }

    content = list(
        (
            await db.execute(
                select(Content)
                .where(Content.project_id == project.id)
                .order_by(Content.created_at.desc())
            )
        ).scalars()
    )

    return {
        "project": project,
        "branding": _resolve_branding(project, user),
        "generated_on": date.today().isoformat(),
        "audit": audit_ctx,
        "keywords": keyword_ctx,
        "content": content,
    }


# Table-based layout (no flexbox) so it renders identically in xhtml2pdf,
# WeasyPrint, and browsers. Branding color is interpolated inline.
_TEMPLATE = Template(
    """<!doctype html>
<html><head><meta charset="utf-8"><title>SEO Report — {{ project.name }}</title>
<style>
  @page { size: A4; margin: 1.5cm; }
  body { font-family: Helvetica, Arial, sans-serif; color: #111827; font-size: 12px; }
  h1 { font-size: 20px; margin: 14px 0 2px; }
  h2 { font-size: 15px; color: {{ branding.color }}; margin-top: 20px; margin-bottom: 4px; }
  .muted { color: #6b7280; }
  .brand { font-size: 22px; font-weight: bold; color: {{ branding.color }}; }
  .n { font-size: 20px; font-weight: bold; }
  table.data { width: 100%; border-collapse: collapse; margin-top: 6px; }
  table.data th, table.data td { text-align: left; padding: 5px 6px;
       border-bottom: 1px solid #eeeeee; font-size: 11px; }
  table.data th { background-color: #f9fafb; }
  table.cards { width: 100%; margin: 10px 0; }
  table.cards td { border: 1px solid #e5e7eb; padding: 8px; vertical-align: top; }
  .sev-critical { color: #dc2626; font-weight: bold; }
  .sev-warning { color: #d97706; font-weight: bold; }
  .footer { margin-top: 24px; font-size: 10px; color: #9ca3af; }
</style></head>
<body>
  <table width="100%"><tr>
    <td class="brand">{{ branding.name }}</td>
    <td align="right" class="muted">Generated {{ generated_on }}</td>
  </tr></table>
  <table width="100%"><tr><td style="background-color: {{ branding.color }}; font-size: 3px;">&nbsp;</td></tr></table>

  <h1>SEO Report — {{ project.name }}</h1>
  <div class="muted">{{ project.domain }}</div>

  <h2>Website Audit</h2>
  {% if audit %}
    <table class="cards"><tr>
      <td width="25%"><div class="muted">SEO Score</div><div class="n">{{ audit.score }}/100</div></td>
      <td width="25%"><div class="muted">Critical</div><div class="n sev-critical">{{ audit.critical }}</div></td>
      <td width="25%"><div class="muted">Warnings</div><div class="n sev-warning">{{ audit.warning }}</div></td>
      <td width="25%"><div class="muted">Info</div><div class="n">{{ audit.info }}</div></td>
    </tr></table>
    <div class="muted">Audited page: {{ audit.url }}</div>
    {% if audit.issues %}
    <table class="data"><thead><tr><th>Severity</th><th>Issue</th><th>Recommendation</th></tr></thead>
    <tbody>
      {% for i in audit.issues %}
      <tr><td class="sev-{{ i.severity }}">{{ i.severity }}</td><td>{{ i.message }}</td><td>{{ i.recommendation }}</td></tr>
      {% endfor %}
    </tbody></table>
    {% endif %}
  {% else %}
    <p class="muted">No completed audit yet for this project.</p>
  {% endif %}

  <h2>Keyword Research</h2>
  <table class="cards"><tr>
    <td width="25%"><div class="muted">Total</div><div class="n">{{ keywords.total }}</div></td>
    <td width="25%"><div class="muted">Related</div><div class="n">{{ keywords.related }}</div></td>
    <td width="25%"><div class="muted">Long-tail</div><div class="n">{{ keywords.long_tail }}</div></td>
    <td width="25%"><div class="muted">Questions</div><div class="n">{{ keywords.question }}</div></td>
  </tr></table>
  {% if keywords.clusters %}<div class="muted">Topic clusters: {{ keywords.clusters | join(", ") }}</div>{% endif %}
  {% if keywords.sample %}
  <table class="data"><thead><tr><th>Keyword</th><th>Type</th><th>Difficulty</th><th>Intent</th></tr></thead>
  <tbody>
    {% for k in keywords.sample %}
    <tr><td>{{ k.term }}</td><td>{{ k.kind }}</td><td>{{ k.difficulty or "-" }}</td><td>{{ k.search_intent or "-" }}</td></tr>
    {% endfor %}
  </tbody></table>
  {% endif %}

  <h2>Content ({{ content | length }})</h2>
  {% if content %}
  <table class="data"><thead><tr><th>Title</th><th>Target keyword</th><th>Type</th><th>Status</th></tr></thead>
  <tbody>
    {% for c in content %}
    <tr><td>{{ c.title }}</td><td>{{ c.target_keyword }}</td><td>{{ c.content_type }}</td><td>{{ c.status }}</td></tr>
    {% endfor %}
  </tbody></table>
  {% else %}<p class="muted">No content generated yet.</p>{% endif %}

  <div class="footer">
    {% if branding.white_label %}{{ branding.name }} — SEO Report{% else %}Generated by RankPilot AI{% endif %}
    &middot; {{ project.domain }} &middot; {{ generated_on }}
  </div>
</body></html>"""
)


async def render_html(db: AsyncSession, project: Project, user: User) -> str:
    context = await _gather_context(db, project, user)
    return _TEMPLATE.render(**context)


async def html_to_pdf(html: str) -> bytes:
    """Render HTML to PDF (off the event loop).

    Prefers WeasyPrint when its native libraries are available (best
    fidelity), otherwise falls back to xhtml2pdf — pure Python, no native
    deps, so PDF works out of the box on Windows without GTK/Pango.
    """
    try:  # WeasyPrint: only if importable (native libs present)
        from weasyprint import HTML  # noqa: F401

        return await asyncio.to_thread(
            lambda: __import__("weasyprint").HTML(string=html).write_pdf()
        )
    except Exception:  # noqa: BLE001 - not installed / missing native libs
        return await asyncio.to_thread(_render_with_xhtml2pdf, html)


def _render_with_xhtml2pdf(html: str) -> bytes:
    import io

    from xhtml2pdf import pisa

    buffer = io.BytesIO()
    result = pisa.CreatePDF(src=html, dest=buffer, encoding="utf-8")
    if result.err:
        raise RuntimeError("PDF rendering failed (xhtml2pdf).")
    return buffer.getvalue()
