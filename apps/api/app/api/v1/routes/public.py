"""Public (no-auth) routes — client share links.

A client with a valid share-link token can view the project's report without
logging in. The link is read-only; revoked links stop working immediately.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.agency import ClientShareLink
from app.models.project import Project
from app.models.user import User
from app.services import email_service, report_service

router = APIRouter()


class ContactRequest(BaseModel):
    """A "request access" / contact-form submission (not a registration)."""

    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    company: str | None = Field(default=None, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)


@router.post("/contact")
async def submit_contact(payload: ContactRequest) -> dict[str, bool]:
    """Forward an access request to the team. Never fails the caller."""
    sent = await email_service.send_contact_email(
        payload.name, payload.email, payload.message, payload.company
    )
    return {"received": True, "emailed": sent}


@router.get("/share/{token}/report", response_class=HTMLResponse)
async def shared_report(
    token: str, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """Render a project's report for a client via a share token (no login)."""
    link = (
        await db.execute(
            select(ClientShareLink).where(ClientShareLink.token == token)
        )
    ).scalar_one_or_none()
    if link is None or link.revoked:
        raise HTTPException(status_code=404, detail="Share link not found")

    project = await db.get(Project, link.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Branding follows the project owner's plan (Agency → white-label).
    owner = await db.get(User, project.owner_id)
    html = await report_service.render_html(db, project, owner)
    return HTMLResponse(content=html)
