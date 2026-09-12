"""Add super-admin and forced-password-change flags to users.

Supports invite-only signup: accounts are created by a super admin and start
with ``must_change_password`` set until the user sets their own password.

Revision ID: 0013_user_admin_flags
Revises: 0012_technical_seo
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_user_admin_flags"
down_revision: Union[str, None] = "0012_technical_seo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "is_superuser")
