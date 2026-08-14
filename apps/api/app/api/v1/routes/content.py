"""AI Content Studio routes."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user
from app.db.base import get_db
from app.models.content import Content
from app.models.user import User
from app.schemas.content import ContentGenerateRequest, ContentRead
from app.services import content_service

router = APIRouter()


@router.post("/generate/stream")
async def generate_content_stream(
    payload: ContentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream content generation as Server-Sent Events.

    Emits `outline`, `section`, `token`, `seo`, and finally `done` (with the
    persisted content id), or `error`.
    """
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        async for sse, result in content_service.stream_generate(payload):
            if result is None:
                if sse:
                    yield sse
                continue
            # Terminal tuple: persist, then emit `done`.
            content = Content(
                project_id=payload.project_id,
                topic=payload.topic,
                target_keyword=payload.target_keyword,
                content_type=payload.content_type,
                title=result.title,
                meta_description=result.meta_description,
                body_markdown=result.body_markdown,
                status="draft",
            )
            db.add(content)
            await db.commit()
            await db.refresh(content)
            yield (
                "event: done\n"
                f"data: {json.dumps({'content_id': str(content.id)})}\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering so tokens flush immediately.
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/generate",
    response_model=ContentRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_content(
    payload: ContentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Content:
    """Generate a content piece (non-streaming) and store it."""
    await ensure_project_access(
        payload.project_id, current_user, db, min_role="editor"
    )

    try:
        result = await content_service.generate(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Content generation failed: {exc}",
        ) from exc

    content = Content(
        project_id=payload.project_id,
        topic=payload.topic,
        target_keyword=payload.target_keyword,
        content_type=payload.content_type,
        title=result.title,
        meta_description=result.meta_description,
        body_markdown=result.body_markdown,
        status="draft",
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.get("", response_model=list[ContentRead])
async def list_content(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Content]:
    """List content for a project the current user owns, newest first."""
    await ensure_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Content)
        .where(Content.project_id == project_id)
        .order_by(Content.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{content_id}", response_model=ContentRead)
async def get_content(
    content_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Content:
    """Fetch a single content piece the current user owns."""
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    await ensure_project_access(content.project_id, current_user, db)
    return content
