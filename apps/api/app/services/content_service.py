"""AI Content Studio service — LangChain content chain.

A three-stage structured prompt chain:

  1. Outline generation      → structured list of section headings
  2. Section drafting        → each section drafted from the outline
  3. SEO optimization pass    → deterministic keyword-density check +
                                meta title/description generation

Exposes a streaming generator (Server-Sent Events) used by the UI and a
run-to-completion helper used by the plain JSON endpoint.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.content import (
    ContentGenerateRequest,
    ContentGenerationResult,
    KeywordDensityReport,
)

# --- Human-readable content-type guidance for the prompts ---------------
_CONTENT_KIND = {
    "blog": "an SEO-optimized blog post",
    "product_description": "a persuasive SEO product description",
    "landing_page": "a high-converting SEO landing page",
}

# Per-content-type structural guidance so each format reads correctly instead
# of every type coming out as a generic article.
_STRUCTURE_GUIDANCE = {
    "blog": (
        "Structure it as a blog article: an engaging introduction that hooks "
        "the reader, several logically-ordered body sections that develop the "
        "topic in depth, and a concise conclusion with a clear takeaway."
    ),
    "product_description": (
        "Structure it as a product description that sells: a compelling "
        "overview/hook, the key features, the concrete benefits those features "
        "deliver to the buyer, and (where relevant) specifications. Keep "
        "sections short, concrete, and persuasive — not a long essay."
    ),
    "landing_page": (
        "Structure it as a high-converting landing page: an attention-grabbing "
        "hero / value proposition, the key benefits, the main features, social "
        "proof or trust signals, and a strong closing call-to-action. Sections "
        "must be punchy, benefit-led, and conversion-focused."
    ),
}


# --- Structured outputs for the deterministic chain stages --------------
class _Outline(BaseModel):
    sections: list[str]


class _Meta(BaseModel):
    meta_title: str
    meta_description: str


def _llm(*, streaming: bool = False, temperature: float = 0.7) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
        streaming=streaming,
    )


# --- Prompt templates ---------------------------------------------------
_OUTLINE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert SEO content strategist. You design clear, "
            "logically-ordered outlines that rank well and read naturally.",
        ),
        (
            "human",
            "Create a section outline for {kind} about \"{topic}\", targeting "
            "the keyword \"{keyword}\". Tone: {tone}. Target length: about "
            "{word_count} words.\n\n"
            "{structure_guidance}\n\n"
            "Return the section headings only (no meta title), ordered "
            "logically. Choose a number of sections appropriate for this "
            "content type and length (a short product description needs few "
            "sections; a long blog post needs more).",
        ),
    ]
)

_SECTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior SEO copywriter. You write engaging, accurate, "
            "human prose and never keyword-stuff.",
        ),
        (
            "human",
            "You are drafting {kind} about \"{topic}\" (tone: {tone}, target "
            "keyword: \"{keyword}\").\n"
            "{structure_guidance}\n\n"
            "Full outline for context:\n{outline}\n\n"
            "Write ONLY the \"{section}\" section in Markdown, beginning with "
            "'## {section}'. Aim for roughly {target_words} words for this "
            "section, matching the format above (e.g. punchy and benefit-led "
            "for a landing page or product description; in-depth for a blog). "
            "Naturally reference the target keyword where it fits. Do not write "
            "any other section.",
        ),
    ]
)

_META_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an SEO specialist who writes click-worthy metadata.",
        ),
        (
            "human",
            "For the content below, write an SEO meta title (<= 60 chars) and a "
            "meta description (140–160 chars). Both must include the keyword "
            "\"{keyword}\" and encourage clicks.\n\nCONTENT:\n{body}",
        ),
    ]
)


# --- Chain stages -------------------------------------------------------
async def _generate_outline(request: ContentGenerateRequest) -> list[str]:
    chain = _OUTLINE_PROMPT | _llm(temperature=0.5).with_structured_output(
        _Outline
    )
    result: _Outline = await chain.ainvoke(
        {
            "kind": _CONTENT_KIND[request.content_type],
            "topic": request.topic,
            "keyword": request.target_keyword,
            "tone": request.tone,
            "word_count": request.word_count,
            "structure_guidance": _STRUCTURE_GUIDANCE[request.content_type],
        }
    )
    return [s.strip() for s in result.sections if s.strip()]


def _section_inputs(
    request: ContentGenerateRequest, outline: list[str], section: str
) -> dict[str, str]:
    # Split the requested total word count across the sections.
    target_words = max(request.word_count // max(len(outline), 1), 60)
    return {
        "kind": _CONTENT_KIND[request.content_type],
        "topic": request.topic,
        "keyword": request.target_keyword,
        "tone": request.tone,
        "structure_guidance": _STRUCTURE_GUIDANCE[request.content_type],
        "outline": "\n".join(f"- {s}" for s in outline),
        "section": section,
        "target_words": str(target_words),
    }


async def _generate_meta(
    request: ContentGenerateRequest, body: str
) -> _Meta:
    chain = _META_PROMPT | _llm(temperature=0.5).with_structured_output(_Meta)
    return await chain.ainvoke(
        {"keyword": request.target_keyword, "body": body}
    )


def compute_density(body: str, keyword: str) -> KeywordDensityReport:
    """Deterministic keyword-density check over the drafted body."""
    plain = re.sub(r"[#*_`>\[\]()\-]", " ", body).lower()
    words = re.findall(r"\w+", plain)
    word_count = len(words)

    kw = keyword.lower().strip()
    occurrences = len(re.findall(re.escape(kw), plain)) if kw else 0
    kw_word_len = len(kw.split()) or 1
    density = (
        round(occurrences * kw_word_len / word_count * 100, 2)
        if word_count
        else 0.0
    )

    if density < 0.5:
        assessment = "low"
        recommendation = (
            "Keyword density is low — work the target keyword and close "
            "variants into a few more sections."
        )
    elif density > 2.5:
        assessment = "high"
        recommendation = (
            "Keyword density is high — reduce repetition to avoid keyword "
            "stuffing; use synonyms instead."
        )
    else:
        assessment = "optimal"
        recommendation = "Keyword density is in a healthy range (0.5–2.5%)."

    return KeywordDensityReport(
        keyword=keyword,
        occurrences=occurrences,
        word_count=word_count,
        density_pct=density,
        assessment=assessment,
        recommendation=recommendation,
    )


# --- Public API ---------------------------------------------------------
async def generate(
    request: ContentGenerateRequest,
) -> ContentGenerationResult:
    """Run the full chain to completion (non-streaming)."""
    outline = await _generate_outline(request)

    draft_llm = _llm(temperature=0.7)
    parts: list[str] = []
    for section in outline:
        chain = _SECTION_PROMPT | draft_llm
        message = await chain.ainvoke(_section_inputs(request, outline, section))
        parts.append(str(message.content).strip())
    body = "\n\n".join(parts).strip()

    meta = await _generate_meta(request, body)
    density = compute_density(body, request.target_keyword)

    return ContentGenerationResult(
        title=meta.meta_title,
        meta_title=meta.meta_title,
        meta_description=meta.meta_description,
        body_markdown=body,
        outline=outline,
        density=density,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_generate(
    request: ContentGenerateRequest,
) -> AsyncGenerator[tuple[str, ContentGenerationResult | None], None]:
    """Stream the chain as SSE strings.

    Yields ``(sse_string, result)`` tuples. ``result`` is ``None`` for every
    event except the terminal one, where it carries the finished content so
    the route can persist it before emitting ``done``.
    """
    try:
        # --- Stage 1: outline ---
        yield _sse("phase", {"phase": "outline", "status": "start"}), None
        outline = await _generate_outline(request)
        yield _sse("outline", {"sections": outline}), None

        # --- Stage 2: section drafting (streamed) ---
        yield _sse("phase", {"phase": "drafting", "status": "start"}), None
        draft_llm = _llm(streaming=True, temperature=0.7)
        parts: list[str] = []
        for index, section in enumerate(outline):
            yield _sse("section", {"index": index, "title": section}), None
            chain = _SECTION_PROMPT | draft_llm
            buffer = ""
            async for chunk in chain.astream(
                _section_inputs(request, outline, section)
            ):
                token = str(chunk.content)
                if token:
                    buffer += token
                    yield _sse("token", {"text": token}), None
            parts.append(buffer.strip())
            yield _sse("token", {"text": "\n\n"}), None
        body = "\n\n".join(parts).strip()

        # --- Stage 3: SEO optimization pass ---
        yield _sse("phase", {"phase": "seo", "status": "start"}), None
        meta = await _generate_meta(request, body)
        density = compute_density(body, request.target_keyword)
        yield (
            _sse(
                "seo",
                {
                    "meta_title": meta.meta_title,
                    "meta_description": meta.meta_description,
                    "density": density.model_dump(),
                },
            ),
            None,
        )

        result = ContentGenerationResult(
            title=meta.meta_title,
            meta_title=meta.meta_title,
            meta_description=meta.meta_description,
            body_markdown=body,
            outline=outline,
            density=density,
        )
        # Terminal event carries the result for the route to persist.
        yield "", result
    except Exception as exc:  # noqa: BLE001 - surface errors over the stream
        yield _sse("error", {"detail": str(exc)}), None
