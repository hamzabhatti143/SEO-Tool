"""Add project_pages (Internal Link Optimizer).

Revision ID: 0002_project_pages
Revises: 0001_initial
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_project_pages"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "project_pages",
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
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column(
            "word_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
        sa.Column(
            "outbound_internal_links", postgresql.JSONB(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "url", name="uq_project_pages_project_url"
        ),
    )
    op.create_index(
        "ix_project_pages_project_id",
        "project_pages",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("project_pages")
