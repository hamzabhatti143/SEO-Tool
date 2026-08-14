"""Internal Link Optimizer service.

Two phases:
  - ``crawl_and_store``: crawl the project's own site, persist each page's
    title, content summary, embedding, and outbound internal links.
  - ``analyze``: from the stored pages, build the internal-link graph,
    detect orphan pages, and suggest semantically-related linking
    opportunities via embedding cosine similarity.
"""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urljoin, urlparse

import httpx
import numpy as np
from bs4 import BeautifulSoup
from openai import AsyncOpenAI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.page import ProjectPage
from app.models.project import Project
from app.schemas.internal_links import (
    AnalysisResponse,
    GraphEdge,
    GraphNode,
    LinkSuggestion,
    PageRead,
)

_USER_AGENT = "RankPilotBot/0.1 (+https://rankpilot.ai/bot)"
_ASSET_RE = re.compile(
    r"\.(?:png|jpe?g|gif|svg|webp|ico|css|js|pdf|zip|mp4|mp3|woff2?|ttf)(?:\?|$)",
    re.IGNORECASE,
)


def _normalize(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _start_url(project: Project) -> str:
    domain = project.domain
    if not urlparse(domain).scheme:
        domain = f"https://{domain}"
    return _normalize(domain)


# --- Crawl + persist ----------------------------------------------------
async def crawl_and_store(
    db: AsyncSession, project: Project
) -> list[ProjectPage]:
    start = _start_url(project)
    base_host = urlparse(start).netloc
    max_pages = settings.INTERNAL_LINK_MAX_PAGES

    queue: list[str] = [start]
    queued: set[str] = {start}
    visited: set[str] = set()
    collected: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=settings.AUDIT_REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        while queue and len(collected) < max_pages:
            url = queue.pop(0)
            visited.add(url)
            try:
                resp = await client.get(url)
            except httpx.HTTPError:
                continue
            if "text/html" not in resp.headers.get("content-type", ""):
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else None
            headings = " ".join(
                h.get_text(strip=True)
                for h in soup.find_all(["h1", "h2", "h3"])
            )
            text = soup.get_text(" ", strip=True)

            outbound: set[str] = set()
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"].strip()
                if not href or href.startswith(
                    ("#", "mailto:", "tel:", "javascript:")
                ):
                    continue
                absolute = urljoin(str(resp.url), href)
                if urlparse(absolute).scheme not in ("http", "https"):
                    continue
                if urlparse(absolute).netloc != base_host:
                    continue
                if _ASSET_RE.search(absolute):
                    continue
                normalized = _normalize(absolute)
                outbound.add(normalized)
                if normalized not in queued and normalized not in visited:
                    queued.add(normalized)
                    queue.append(normalized)

            collected.append(
                {
                    "url": url,
                    "title": title,
                    "text": text,
                    "headings": headings,
                    "outbound": sorted(outbound),
                }
            )

    embeddings = await _embed(
        [
            f"{c['title'] or ''} {c['headings']} {c['text'][:1500]}"
            for c in collected
        ]
    )

    # Replace any previous crawl for this project.
    await db.execute(
        delete(ProjectPage).where(ProjectPage.project_id == project.id)
    )
    pages: list[ProjectPage] = []
    for i, c in enumerate(collected):
        page = ProjectPage(
            project_id=project.id,
            url=c["url"],
            title=c["title"],
            content_summary=(c["text"][:500] or None),
            word_count=len(c["text"].split()),
            embedding=embeddings[i] if embeddings else None,
            outbound_internal_links=c["outbound"],
        )
        db.add(page)
        pages.append(page)
    await db.commit()
    for page in pages:
        await db.refresh(page)
    return pages


async def _embed(texts: list[str]) -> list[list[float]] | None:
    if not texts or not settings.OPENAI_API_KEY:
        return None
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL, input=texts
        )
        return [d.embedding for d in resp.data]
    except Exception:  # noqa: BLE001 - embeddings are best-effort
        return None


# --- Analysis -----------------------------------------------------------
async def analyze(db: AsyncSession, project: Project) -> AnalysisResponse:
    pages = list(
        (
            await db.execute(
                select(ProjectPage).where(
                    ProjectPage.project_id == project.id
                )
            )
        ).scalars()
    )
    if not pages:
        return AnalysisResponse(
            page_count=0, nodes=[], edges=[], suggestions=[], orphans=[]
        )

    id_of = {p.url: str(p.id) for p in pages}
    by_url = {p.url: p for p in pages}
    start = _start_url(project)

    # Edges (only internal links whose target was also crawled).
    edge_set: set[tuple[str, str]] = set()
    for p in pages:
        for link in p.outbound_internal_links or []:
            if link in by_url and link != p.url:
                edge_set.add((str(p.id), id_of[link]))

    inbound = Counter(t for _, t in edge_set)
    outbound = Counter(s for s, _ in edge_set)

    nodes: list[GraphNode] = []
    orphans: list[PageRead] = []
    for p in pages:
        nid = str(p.id)
        ib = inbound.get(nid, 0)
        is_orphan = ib == 0 and p.url != start
        nodes.append(
            GraphNode(
                id=nid,
                label=p.title or p.url,
                url=p.url,
                inbound=ib,
                outbound=outbound.get(nid, 0),
                is_orphan=is_orphan,
            )
        )
        if is_orphan:
            orphans.append(PageRead.model_validate(p))

    edges = [GraphEdge(source=s, target=t) for s, t in edge_set]
    suggestions = _suggest(pages)
    return AnalysisResponse(
        page_count=len(pages),
        nodes=nodes,
        edges=edges,
        suggestions=suggestions,
        orphans=orphans,
    )


def _anchor(page: ProjectPage) -> str:
    if page.title:
        return page.title[:80]
    slug = urlparse(page.url).path.rstrip("/").split("/")[-1] or page.url
    return slug.replace("-", " ").replace("_", " ")[:80]


def _suggest(pages: list[ProjectPage]) -> list[LinkSuggestion]:
    embedded = [p for p in pages if p.embedding]
    if len(embedded) < 2:
        return []

    X = np.array([p.embedding for p in embedded], dtype=float)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = X / norms
    sims = X @ X.T

    threshold = settings.INTERNAL_LINK_SIM_THRESHOLD
    top_k = settings.INTERNAL_LINK_TOP_K
    suggestions: list[LinkSuggestion] = []

    for i, src in enumerate(embedded):
        existing = set(src.outbound_internal_links or [])
        order = np.argsort(-sims[i])
        added = 0
        for j in order:
            if j == i or added >= top_k:
                if added >= top_k:
                    break
                continue
            target = embedded[j]
            if target.url in existing or target.url == src.url:
                continue
            score = float(sims[i][j])
            if score < threshold:
                break  # sorted descending — nothing better remains
            suggestions.append(
                LinkSuggestion(
                    from_url=src.url,
                    from_title=src.title or src.url,
                    to_url=target.url,
                    to_title=target.title or target.url,
                    anchor_text=_anchor(target),
                    similarity=round(score, 3),
                )
            )
            added += 1

    suggestions.sort(key=lambda s: s.similarity, reverse=True)
    return suggestions[:100]
