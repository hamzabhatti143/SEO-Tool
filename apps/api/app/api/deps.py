"""Shared FastAPI dependencies (authentication, ownership checks)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import feature_flags
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


def require_feature(
    feature: str,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Build a dependency that gates an endpoint to a feature's tier.

    Returns the current user when their subscription tier includes ``feature``;
    otherwise raises 403 with a clear "Upgrade to Premium" message. Apply it
    per-handler or at the router level, e.g.::

        router = APIRouter(
            dependencies=[Depends(require_feature("backlink_center"))]
        )
    """

    async def _dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not feature_flags.tier_allows(current_user.plan, feature):
            label = feature_flags.feature_label(feature)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{label} is a Premium feature. Upgrade to Premium "
                "to unlock it.",
            )
        return current_user

    return _dependency
