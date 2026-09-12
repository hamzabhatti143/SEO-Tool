"""Authentication routes — login, current user, password change.

FastAPI is the source of truth for users and issues the HS256 JWTs that
both the Next.js app and this API validate with ``SECRET_KEY``. Public
self-signup has been removed: accounts are created by a super admin (see
``app.api.v1.routes.admin``), so this module only signs existing users in.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, TokenResponse
from app.schemas.user import UserRead

router = APIRouter()


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email (as ``username``) + password."""
    user = await _get_user_by_email(db, form_data.username)
    if user is None or not verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended. Contact your administrator.",
        )

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user."""
    return current_user


@router.post("/change-password", response_model=UserRead)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Set a new password and clear the ``must_change_password`` flag.

    For a forced first-login change (``must_change_password`` is set) the
    caller already authenticated with the temporary password, so the current
    password is not required. A voluntary change requires the current password.
    """
    if not current_user.must_change_password:
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    await db.commit()
    await db.refresh(current_user)
    return current_user
