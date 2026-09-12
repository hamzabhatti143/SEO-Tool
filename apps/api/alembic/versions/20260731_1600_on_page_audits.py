"""Add on_page_audits table (multi-keyword On-Page Optimizer runs).

Stores the optimizer's target keywords as a JSON array (``keywords``), the
primary keyword, the analyzed URL, and the combined score.

Revision ID: 0016_on_page_audits
Revises: 0015_account_status_admin_isolation
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016_on_page_audits"
down_revision: Union[str, None] = "0015_account_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "on_page_audits",
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
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("keywords", postgresql.JSONB(), nullable=False),
        sa.Column("primary_keyword", sa.String(length=255), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_on_page_audits_project_id", "on_page_audits", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_on_page_audits_project_id", table_name="on_page_audits")
    op.drop_table("on_page_audits")
