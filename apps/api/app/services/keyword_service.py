"""Keyword Research service.

Runs the OpenAI keyword agent, then enriches the results with:
  - topic clustering (text-embedding-3-small + cosine similarity)
  - AI-generated cluster labels
  - Google Trends signal (best-effort, via pytrends)

Clustering/labeling/trends are all best-effort — if any step fails the
keywords are still returned, just without that enrichment.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np
from agents import Runner
from openai import AsyncOpenAI

from app.agents.cluster_label_agent import cluster_label_agent
from app.agents.keyword_agent import keyword_agent
from app.core.config import settings
from app.schemas.keyword import (
    N_LONG_TAIL,
    N_QUESTIONS,
    N_RELATED,
    KeywordAgentOutput,
    KeywordResearchRequest,
)
from app.services import trends_service

_QUESTIONS_LABEL = "People Also Ask"


@dataclass
class FlatKeyword:
    """A keyword flattened from the agent output, tagged and enriched."""

    term: str
    kind: str
    difficulty: str
    search_intent: str
    cluster_id: int | None = None
    cluster_label: str | None = None
    trend_score: int | None = None
    trend_direction: str | None = None


async def research_keywords(
    request: KeywordResearchRequest,
) -> list[FlatKeyword]:
    """Generate, cluster, label, and trend-enrich keyword suggestions."""
    result = await Runner.run(
        keyword_agent, f"Seed keyword: {request.seed_keyword}"
    )
    output: KeywordAgentOutput = result.final_output

    flat: list[FlatKeyword] = []
    for kind, items, cap in (
        ("related", output.related, N_RELATED),
        ("long_tail", output.long_tail, N_LONG_TAIL),
        ("question", output.questions, N_QUESTIONS),
    ):
        for item in items[:cap]:
            flat.append(
                FlatKeyword(
                    term=item.term,
                    kind=kind,
                    difficulty=item.difficulty,
                    search_intent=item.search_intent,
                )
            )

    await _cluster_and_label(flat)
    for kw in flat:
        if kw.kind == "question":
            kw.cluster_label = _QUESTIONS_LABEL

    await _enrich_trends(flat)
    return flat


# --- Clustering ---------------------------------------------------------
async def _cluster_and_label(flat: list[FlatKeyword]) -> None:
    """Cluster related/long-tail keywords in place (best-effort)."""
    clusterable = [kw for kw in flat if kw.kind != "question"]
    if not clusterable or not settings.OPENAI_API_KEY:
        return

    try:
        terms = [kw.term for kw in clusterable]
        vectors = await _embed(terms)
        assigned, normed = _cluster(vectors, settings.KEYWORD_CLUSTER_THRESHOLD)
        num_clusters = (max(assigned) + 1) if assigned else 0

        clusters_terms = [
            [terms[i] for i in range(len(terms)) if assigned[i] == cid]
            for cid in range(num_clusters)
        ]
        labels = await _label_clusters(clusters_terms)

        for cid in range(num_clusters):
            label = (
                labels[cid]
                if labels
                else _representative(terms, normed, assigned, cid)
            )
            for i, kw in enumerate(clusterable):
                if assigned[i] == cid:
                    kw.cluster_id = cid
                    kw.cluster_label = label
    except Exception:  # noqa: BLE001 - clustering is best-effort
        return


async def _embed(terms: list[str]) -> list[list[float]]:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    resp = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL, input=terms
    )
    return [d.embedding for d in resp.data]


def _cluster(
    vectors: list[list[float]], threshold: float
) -> tuple[list[int], np.ndarray]:
    """Greedy single-pass cosine clustering. Returns (assignments, unit vecs)."""
    X = np.array(vectors, dtype=float)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = X / norms

    assigned = [-1] * len(X)
    centroids: list[list] = []  # [sum_vector, count]
    next_id = 0

    for i in range(len(X)):
        best, best_sim = -1, threshold
        for cid, (csum, count) in enumerate(centroids):
            centroid = csum / count
            cnorm = np.linalg.norm(centroid)
            if cnorm == 0:
                continue
            sim = float(np.dot(X[i], centroid / cnorm))
            if sim >= best_sim:
                best, best_sim = cid, sim
        if best == -1:
            centroids.append([X[i].copy(), 1])
            assigned[i] = next_id
            next_id += 1
        else:
            centroids[best][0] += X[i]
            centroids[best][1] += 1
            assigned[i] = best

    return assigned, X


def _representative(
    terms: list[str], normed: np.ndarray, assigned: list[int], cid: int
) -> str:
    """The term closest to the cluster centroid — a sensible fallback label."""
    idxs = [i for i, a in enumerate(assigned) if a == cid]
    sub = normed[idxs]
    centroid = sub.mean(axis=0)
    cnorm = np.linalg.norm(centroid) or 1.0
    sims = sub @ (centroid / cnorm)
    return terms[idxs[int(np.argmax(sims))]]


async def _label_clusters(clusters_terms: list[list[str]]) -> list[str] | None:
    """Ask the AI for a label per cluster (best-effort; None on failure)."""
    if not clusters_terms:
        return None
    try:
        listing = "\n".join(
            f"Cluster {i}: {', '.join(ts)}"
            for i, ts in enumerate(clusters_terms)
        )
        result = await Runner.run(
            cluster_label_agent,
            f"Label these {len(clusters_terms)} clusters:\n{listing}",
        )
        labels = [label.strip() for label in result.final_output.labels]
        if len(labels) == len(clusters_terms):
            return labels
    except Exception:  # noqa: BLE001
        pass
    return None


# --- Trends -------------------------------------------------------------
async def _enrich_trends(flat: list[FlatKeyword]) -> None:
    """Attach Google Trends data in place (best-effort, off the event loop)."""
    try:
        terms = [kw.term for kw in flat]
        trend_map = await asyncio.to_thread(trends_service.fetch_trends, terms)
    except Exception:  # noqa: BLE001
        return
    for kw in flat:
        data = trend_map.get(kw.term)
        if data:
            kw.trend_score = data["score"]
            kw.trend_direction = data["direction"]
