"""Super-admin routes, mounted at ``/api/admin`` (outside the /api/v1 tree).

Auth here is fully isolated from regular users: ``/api/admin/login`` checks the
SUPER_ADMIN_* env credentials and issues an admin-scoped JWT; every other route
is guarded by ``require_super_admin``. Account management operates on the Users
table but the admin identity itself never lives there.
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.admin.deps import require_super_admin
from app.core.config import settings
from app.core.security import create_admin_token, generate_temp_password, hash_password
from app.db.base import get_db
from app.models.project import Project
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.admin import (
    AccountCreate,
    AccountCreateResponse,
    AccountRead,
    AccountStatusUpdate,
    AccountUpdate,
    AdminLoginRequest,
    AdminStats,
    AdminTokenResponse,
)
from app.services import email_service

router = APIRouter()


def _credentials_valid(username: str, password: str) -> bool:
    """Constant-time check against the env credentials (disabled if unset)."""
    expected_user = settings.SUPER_ADMIN_USERNAME
    expected_pass = settings.SUPER_ADMIN_PASSWORD
    if not expected_user or not expected_pass:
        return False
    user_ok = secrets.compare_digest(username, expected_user)
    pass_ok = secrets.compare_digest(password, expected_pass)
    return user_ok and pass_ok


async def _project_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count(Project.id)).where(Project.owner_id == user_id)
        )
    ).scalar_one()


async def _to_account(db: AsyncSession, user: User) -> AccountRead:
    account = AccountRead.model_validate(user)
    account.project_count = await _project_count(db, user.id)
    return account


async def _get_user_or_404(db: AsyncSession, account_id: uuid.UUID) -> User:
    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.subscription))
            .where(User.id == account_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return user


# --- Auth ---------------------------------------------------------------
@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(payload: AdminLoginRequest) -> AdminTokenResponse:
    """Authenticate the super admin against env credentials; issue an admin JWT."""
    if not _credentials_valid(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials",
        )
    token = create_admin_token(payload.username)
    return AdminTokenResponse(access_token=token)


# --- Accounts -----------------------------------------------------------
@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    _: str = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AccountRead]:
    """List all user accounts with tier, status, created date, project count."""
    rows = (
        await db.execute(
            select(User, func.count(Project.id))
            .outerjoin(Project, Project.owner_id == User.id)
            .group_by(User.id)
            .order_by(User.created_at.desc())
        )
    ).all()
    accounts: list[AccountRead] = []
    for user, count in rows:
        account = AccountRead.model_validate(user)
        account.project_count = count or 0
        accounts.append(account)
    return accounts


@router.get("/stats", response_model=AdminStats)
async def account_stats(
    _: str = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminStats:
    """Aggregate counts for the dashboard header."""
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    premium = (
        await db.execute(
            select(func.count(User.id)).where(User.plan == "premium")
        )
    ).scalar_one()
    suspended = (
        await db.execute(
            select(func.count(User.id)).where(User.status == "suspended")
        )
    ).scalar_one()
    return AdminStats(
        total=total,
        premium=premium,
        standard=total - premium,
        suspended=suspended,
        active=total - suspended,
    )


@router.post(
    "/accounts",
    response_model=AccountCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    payload: AccountCreate,
    _: str = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AccountCreateResponse:
    """Create an account (invite flow): temp password + forced first-login change."""
    existing = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Use the admin-provided password if given; otherwise generate a temporary
    # one and force a change on first login.
    admin_set = payload.password is not None
    password = payload.password or generate_temp_password()
    user = User(
        email=payload.email,
        hashed_password=hash_password(password),
        full_name=payload.full_name,
        plan=payload.plan,
        status="active",
        must_change_password=not admin_set,
    )
    user.subscription = Subscription(tier=payload.plan, status="active")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    emailed = False
    if payload.send_email:
        emailed = await email_service.send_new_account_email(
            user.email, password, user.full_name
        )

    return AccountCreateResponse(
        account=await _to_account(db, user),
        temporary_password=password,
        emailed=emailed,
    )


@router.patch("/accounts/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    _: str = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AccountRead:
    """Edit account details and/or change the subscription tier."""
    user = await _get_user_or_404(db, account_id)

    data = payload.model_dump(exclude_unset=True)
    if "full_name" in data:
        user.full_name = data["full_name"]
    if data.get("plan"):
        # Keep the denormalized User.plan and the Subscription row in sync.
        user.plan = data["plan"]
        if user.subscription is not None:
            user.subscription.tier = data["plan"]
        else:
            user.subscription = Subscription(tier=data["plan"], status="active")
    if data.get("password"):
        # Admin set a new password directly — it's the working password, so
        # clear the forced-change flag.
        user.hashed_password = hash_password(data["password"])
        user.must_change_password = False

    await db.commit()
    await db.refresh(user)
    return await _to_account(db, user)


@router.patch("/accounts/{account_id}/status", response_model=AccountRead)
async def update_account_status(
    account_id: uuid.UUID,
    payload: AccountStatusUpdate,
    _: str = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AccountRead:
    """Suspend or reactivate an account (suspended accounts cannot log in)."""
    user = await _get_user_or_404(db, account_id)
    user.status = payload.status
    await db.commit()
    await db.refresh(user)
    return await _to_account(db, user)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    _: str = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete an account; Postgres ON DELETE CASCADE removes their data."""
    user = (
        await db.execute(select(User).where(User.id == account_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    # DB-level cascade (projects + all project children + subscription).
    await db.execute(delete(User).where(User.id == account_id))
    await db.commit()
