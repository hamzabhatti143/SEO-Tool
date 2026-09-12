"""Add technical_seo_issues table (extended detection engine).

Stores per-scan technical-SEO findings (broken links, redirect chains,
canonical problems, sitemap errors, duplicate content, orphan pages, mixed
content, missing alt text) with a per-finding ``fix_confidence`` and
lifecycle ``status``.

Revision ID: 0017_technical_seo_issues
Revises: 0016_on_page_audits
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0017_technical_seo_issues"
down_revision: Union[str, None] = "0016_on_page_audits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "technical_seo_issues",
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
        sa.Column("issue_type", sa.String(length=40), nullable=False),
        sa.Column("page_url", sa.String(length=2048), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column(
            "fix_confidence",
            sa.String(length=16),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="open",
            nullable=False,
        ),
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
        "ix_technical_seo_issues_project_id",
        "technical_seo_issues",
        ["project_id"],
    )
    op.create_index(
        "ix_technical_seo_issues_issue_type",
        "technical_seo_issues",
        ["issue_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_technical_seo_issues_issue_type", table_name="technical_seo_issues"
    )
    op.drop_index(
        "ix_technical_seo_issues_project_id", table_name="technical_seo_issues"
    )
    op.drop_table("technical_seo_issues")
