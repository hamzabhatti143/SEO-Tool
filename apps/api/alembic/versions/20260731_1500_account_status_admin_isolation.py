"""Add account status; drop the now-unused user-level super-admin flag.

The super admin is now an isolated, env-credentialed system (see
``app.admin``) that never lives in the Users table, so ``users.is_superuser``
is removed. ``users.status`` (active | suspended) is added so the super admin
can suspend/reactivate accounts; suspended accounts are blocked at login.

Revision ID: 0015_account_status
Revises: 0014_two_tier_subscription
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic. NOTE: keep <=32 chars — Alembic's
# alembic_version.version_num column is VARCHAR(32).
revision: str = "0015_account_status"
down_revision: Union[str, None] = "0014_two_tier_subscription"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),
    )
    op.drop_column("users", "is_superuser")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.drop_column("users", "status")
