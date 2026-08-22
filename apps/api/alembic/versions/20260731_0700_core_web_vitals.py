"""Add core_web_vitals (Website Audit → Performance / Core Web Vitals).

Revision ID: 0007_core_web_vitals
Revises: 0006_agency_mode
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_core_web_vitals"
down_revision: Union[str, None] = "0006_agency_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "core_web_vitals",
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
        sa.Column("lcp", sa.Float(), nullable=True),
        sa.Column("inp", sa.Float(), nullable=True),
        sa.Column("cls", sa.Float(), nullable=True),
        sa.Column("performance_score", sa.Float(), nullable=True),
        sa.Column("lcp_element", sa.String(length=1024), nullable=True),
        sa.Column(
            "inp_is_estimated",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("issues_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "scanned_at",
            sa.DateTime(timezone=True),
            server_default=_TS,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_core_web_vitals_project_id",
        "core_web_vitals",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_web_vitals_project_id", table_name="core_web_vitals"
    )
    op.drop_table("core_web_vitals")
