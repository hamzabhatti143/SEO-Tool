"""AI SEO Assistant routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.assistant import ChatRequest
from app.services import assistant_service

router = APIRouter()


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream an SEO Assistant reply (SSE). Tools read this project's data."""
    await ensure_project_access(payload.project_id, current_user, db)
    return StreamingResponse(
        assistant_service.stream_chat(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
