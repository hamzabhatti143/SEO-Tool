"""Collapse subscription tiers to standard | premium.

Signup is invite-only and an admin assigns the plan, so the old
free/pro/agency tiers become two paid tiers: the former top tier (agency)
maps to ``premium`` (full access, incl. Backlink Center, Automation, Agency
Mode and white-label reports); everything else maps to ``standard``.

Revision ID: 0014_two_tier_subscription
Revises: 0013_user_admin_flags
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_two_tier_subscription"
down_revision: Union[str, None] = "0013_user_admin_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migrate existing data: agency -> premium, all others -> standard.
    op.execute(
        "UPDATE subscriptions SET tier = "
        "CASE WHEN tier = 'agency' THEN 'premium' ELSE 'standard' END"
    )
    op.execute(
        "UPDATE users SET plan = "
        "CASE WHEN plan = 'agency' THEN 'premium' ELSE 'standard' END"
    )
    # Update column defaults for new rows.
    op.alter_column("subscriptions", "tier", server_default="standard")
    op.alter_column("users", "plan", server_default="standard")


def downgrade() -> None:
    # Best-effort reversal: premium -> agency, standard -> free.
    op.alter_column("subscriptions", "tier", server_default="free")
    op.alter_column("users", "plan", server_default="free")
    op.execute(
        "UPDATE subscriptions SET tier = "
        "CASE WHEN tier = 'premium' THEN 'agency' ELSE 'free' END"
    )
    op.execute(
        "UPDATE users SET plan = "
        "CASE WHEN plan = 'premium' THEN 'agency' ELSE 'free' END"
    )
