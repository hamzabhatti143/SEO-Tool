"""Add rank tracking (tracked_keywords, rank_snapshots).

Revision ID: 0003_rank_tracking
Revises: 0002_project_pages
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_rank_tracking"
down_revision: Union[str, None] = "0002_project_pages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "tracked_keywords",
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
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "keyword", name="uq_tracked_keywords_project_keyword"
        ),
    )
    op.create_index(
        "ix_tracked_keywords_project_id",
        "tracked_keywords",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "rank_snapshots",
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
        sa.Column(
            "tracked_keyword_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(
            ["tracked_keyword_id"],
            ["tracked_keywords.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tracked_keyword_id",
            "checked_on",
            name="uq_rank_snapshots_keyword_date",
        ),
    )
    op.create_index(
        "ix_rank_snapshots_tracked_keyword_id",
        "rank_snapshots",
        ["tracked_keyword_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("rank_snapshots")
    op.drop_table("tracked_keywords")
