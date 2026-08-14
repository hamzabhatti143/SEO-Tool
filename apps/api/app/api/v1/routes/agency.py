"""Agency Mode routes: team members, invites, and client share links.

The management router is gated to the Agency subscription tier via
`require_agency`, and each action further requires admin/owner on the target
project. Accepting an invite lives on a separate (non-gated) router so an
invited teammate on any plan can join.
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_project_access,
    get_current_user,
    require_agency,
)
from app.db.base import get_db
from app.models.agency import ClientShareLink, ProjectInvite, ProjectMember
from app.models.user import User
from app.schemas.agency import (
    InviteAccept,
    InviteAcceptResult,
    InviteCreate,
    InviteRead,
    MemberRead,
    MemberRoleUpdate,
    ShareLinkCreate,
    ShareLinkRead,
)

# Agency-tier-gated management router.
router = APIRouter(dependencies=[Depends(require_agency)])
# Invite acceptance is available to any authenticated user (invitees may be
# on any plan), so it lives on a separate router without the agency gate.
invite_router = APIRouter()


# --- Team members -------------------------------------------------------
@router.get("/projects/{project_id}/members", response_model=list[MemberRead])
async def list_members(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberRead]:
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    rows = (
        await db.execute(
            select(ProjectMember, User.email)
            .join(User, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id)
        )
    ).all()
    return [
        MemberRead(
            id=m.id,
            user_id=m.user_id,
            email=email,
            role=m.role,
            created_at=m.created_at,
        )
        for m, email in rows
    ]


@router.patch(
    "/projects/{project_id}/members/{member_id}", response_model=MemberRead
)
async def update_member_role(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    member = await db.get(ProjectMember, member_id)
    if member is None or member.project_id != project_id:
        raise HTTPException(status_code=404, detail="Member not found")
    member.role = payload.role
    await db.commit()
    await db.refresh(member)
    user = await db.get(User, member.user_id)
    return MemberRead(
        id=member.id,
        user_id=member.user_id,
        email=user.email if user else "",
        role=member.role,
        created_at=member.created_at,
    )


@router.delete(
    "/projects/{project_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    member = await db.get(ProjectMember, member_id)
    if member is None or member.project_id != project_id:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    await db.commit()


# --- Invites ------------------------------------------------------------
@router.get("/projects/{project_id}/invites", response_model=list[InviteRead])
async def list_invites(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectInvite]:
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    return list(
        (
            await db.execute(
                select(ProjectInvite).where(
                    ProjectInvite.project_id == project_id,
                    ProjectInvite.accepted.is_(False),
                )
            )
        ).scalars()
    )


@router.post(
    "/projects/{project_id}/invites",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    project_id: uuid.UUID,
    payload: InviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectInvite:
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    invite = ProjectInvite(
        project_id=project_id,
        email=payload.email,
        role=payload.role,
        token=secrets.token_urlsafe(32),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


@invite_router.post("/accept", response_model=InviteAcceptResult)
async def accept_invite(
    payload: InviteAccept,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteAcceptResult:
    """Accept an invite (any authenticated user). Joins the project's team."""
    invite = (
        await db.execute(
            select(ProjectInvite).where(ProjectInvite.token == payload.token)
        )
    ).scalar_one_or_none()
    if invite is None or invite.accepted:
        raise HTTPException(status_code=404, detail="Invite not found or used")

    existing = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == invite.project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            ProjectMember(
                project_id=invite.project_id,
                user_id=current_user.id,
                role=invite.role,
            )
        )
    invite.accepted = True
    await db.commit()
    return InviteAcceptResult(project_id=invite.project_id, role=invite.role)


# --- Client share links -------------------------------------------------
@router.get(
    "/projects/{project_id}/share-links", response_model=list[ShareLinkRead]
)
async def list_share_links(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ClientShareLink]:
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    return list(
        (
            await db.execute(
                select(ClientShareLink).where(
                    ClientShareLink.project_id == project_id
                )
            )
        ).scalars()
    )


@router.post(
    "/projects/{project_id}/share-links",
    response_model=ShareLinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_share_link(
    project_id: uuid.UUID,
    payload: ShareLinkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientShareLink:
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    link = ClientShareLink(
        project_id=project_id,
        token=secrets.token_urlsafe(24),
        label=payload.label,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.delete(
    "/projects/{project_id}/share-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_share_link(
    project_id: uuid.UUID,
    link_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_project_access(project_id, current_user, db, min_role="admin")
    link = await db.get(ClientShareLink, link_id)
    if link is None or link.project_id != project_id:
        raise HTTPException(status_code=404, detail="Share link not found")
    link.revoked = True
    await db.commit()
