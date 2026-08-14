"""Shared FastAPI dependencies (authentication, ownership checks)."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import JWTError, decode_access_token
from app.db.base import get_db
from app.models.agency import ROLE_ORDER, ProjectMember
from app.models.project import Project
from app.models.user import User

# tokenUrl is relative to the server root so Swagger's "Authorize" works.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer JWT."""
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise _CREDENTIALS_EXC
        user_id = uuid.UUID(subject)
    except (JWTError, ValueError) as exc:
        raise _CREDENTIALS_EXC from exc

    user = await db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_EXC
    return user


async def resolve_project_role(
    project: Project, current_user: User, db: AsyncSession
) -> str | None:
    """Return the caller's role on a project: owner|admin|editor|viewer|None."""
    if project.owner_id == current_user.id:
        return "owner"
    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    return member.role if member else None


async def ensure_project_access(
    project_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    min_role: str = "viewer",
) -> Project:
    """Return the project if the caller has at least ``min_role`` on it.

    Access is granted to the owner or any team member (Agency Mode) whose role
    meets ``min_role`` (viewer < editor < admin < owner). 404 when the caller
    has no access at all (so we never reveal a project exists); 403 when they
    are a member but lack the required role.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    role = await resolve_project_role(project, current_user, db)
    if role is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if ROLE_ORDER[role] < ROLE_ORDER[min_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires the '{min_role}' role or higher.",
        )
    return project


async def ensure_project_owner(
    project_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Project:
    """Backwards-compatible owner/admin-level check (management operations)."""
    return await ensure_project_access(
        project_id, current_user, db, min_role="admin"
    )


async def require_agency(current_user: User = Depends(get_current_user)) -> User:
    """Gate Agency-Mode endpoints to the Agency subscription tier."""
    if current_user.plan != "agency":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency Mode requires the Agency subscription plan.",
        )
    return current_user
