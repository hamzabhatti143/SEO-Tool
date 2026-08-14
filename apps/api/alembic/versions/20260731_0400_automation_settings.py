"""Add automation_settings.

Revision ID: 0005_automation_settings
Revises: 0004_project_branding
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_automation_settings"
down_revision: Union[str, None] = "0004_project_branding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")
_FALSE = sa.text("false")
_TRUE = sa.text("true")


def upgrade() -> None:
    op.create_table(
        "automation_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_TS,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_TS,
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "weekly_audit", sa.Boolean(), server_default=_FALSE, nullable=False
        ),
        sa.Column(
            "broken_link_monitoring",
            sa.Boolean(),
            server_default=_FALSE,
            nullable=False,
        ),
        sa.Column(
            "competitor_monitoring",
            sa.Boolean(),
            server_default=_FALSE,
            nullable=False,
        ),
        sa.Column(
            "email_notifications",
            sa.Boolean(),
            server_default=_TRUE,
            nullable=False,
        ),
        sa.Column(
            "notify_rank_drops",
            sa.Boolean(),
            server_default=_TRUE,
            nullable=False,
        ),
        sa.Column(
            "notify_broken_links",
            sa.Boolean(),
            server_default=_TRUE,
            nullable=False,
        ),
        sa.Column(
            "weekly_summary", sa.Boolean(), server_default=_TRUE, nullable=False
        ),
        sa.Column("audit_url", sa.String(length=2048), nullable=True),
        sa.Column("monitor_url", sa.String(length=2048), nullable=True),
        sa.Column("competitor_urls", postgresql.JSONB(), nullable=True),
        sa.Column("notification_email", sa.String(length=320), nullable=True),
        sa.Column("last_broken_links", postgresql.JSONB(), nullable=True),
        sa.Column("competitor_hashes", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Matches the model's `unique=True, index=True` (a unique index, mirroring
    # the subscriptions.user_id pattern).
    op.create_index(
        "ix_automation_settings_project_id",
        "automation_settings",
        ["project_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("automation_settings")
