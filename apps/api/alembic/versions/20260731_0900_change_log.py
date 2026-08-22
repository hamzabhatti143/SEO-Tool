"""Add change_log (CWV fix orchestration).

Revision ID: 0009_change_log
Revises: 0008_platform_connectors
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_change_log"
down_revision: Union[str, None] = "0008_platform_connectors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "change_log",
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
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("external_change_id", sa.String(length=255), nullable=True),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("cwv_score_before", sa.Float(), nullable=True),
        sa.Column("cwv_score_after", sa.Float(), nullable=True),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=_TS,
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="applied",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_change_log_project_id",
        "change_log",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_change_log_project_id", table_name="change_log")
    op.drop_table("change_log")
