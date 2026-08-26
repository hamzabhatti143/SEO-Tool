"""Add technical-SEO audit tables (schema / robots.txt / llms.txt).

Revision ID: 0012_technical_seo
Revises: 0011_cwv_pagespeed_full
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012_technical_seo"
down_revision: Union[str, None] = "0011_cwv_pagespeed_full"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def _base_columns() -> list:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "schema_audits",
        *_base_columns(),
        sa.Column("page_url", sa.String(length=2048), nullable=False),
        sa.Column("schema_type", sa.String(length=128), nullable=False),
        sa.Column(
            "fmt", sa.String(length=16), server_default="json-ld", nullable=False
        ),
        sa.Column(
            "is_valid", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("missing_properties", postgresql.JSONB(), nullable=True),
        sa.Column("raw_schema", postgresql.JSONB(), nullable=True),
        sa.Column(
            "detected_at",
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
        "ix_schema_audits_project_id", "schema_audits", ["project_id"]
    )

    op.create_table(
        "robots_audits",
        *_base_columns(),
        sa.Column(
            "exists", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("parsed_rules", postgresql.JSONB(), nullable=True),
        sa.Column("issues_found", postgresql.JSONB(), nullable=True),
        sa.Column(
            "checked_at",
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
        "ix_robots_audits_project_id", "robots_audits", ["project_id"]
    )

    op.create_table(
        "llms_txt_audits",
        *_base_columns(),
        sa.Column(
            "exists", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column(
            "follows_spec_format",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "checked_at",
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
        "ix_llms_txt_audits_project_id", "llms_txt_audits", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_llms_txt_audits_project_id", table_name="llms_txt_audits")
    op.drop_table("llms_txt_audits")
    op.drop_index("ix_robots_audits_project_id", table_name="robots_audits")
    op.drop_table("robots_audits")
    op.drop_index("ix_schema_audits_project_id", table_name="schema_audits")
    op.drop_table("schema_audits")
