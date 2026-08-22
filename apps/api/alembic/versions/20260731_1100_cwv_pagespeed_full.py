"""Reshape core_web_vitals for the full PageSpeed Insights report.

Adds strategy, FCP/TBT/Speed Index, field_inp, the a11y/best-practices/seo
category scores, and report_json (insights/diagnostics/passed/screenshots/
metadata/runs). Drops the old single-report columns (inp, inp_is_estimated,
data_source, lcp_element, issues_json).

Revision ID: 0011_cwv_pagespeed_full
Revises: 0010_cwv_data_source
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011_cwv_pagespeed_full"
down_revision: Union[str, None] = "0010_cwv_data_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "core_web_vitals",
        sa.Column(
            "strategy",
            sa.String(length=10),
            server_default="mobile",
            nullable=False,
        ),
    )
    op.add_column("core_web_vitals", sa.Column("fcp", sa.Float(), nullable=True))
    op.add_column("core_web_vitals", sa.Column("tbt", sa.Float(), nullable=True))
    op.add_column(
        "core_web_vitals", sa.Column("speed_index", sa.Float(), nullable=True)
    )
    op.add_column(
        "core_web_vitals", sa.Column("field_inp", sa.Float(), nullable=True)
    )
    op.add_column(
        "core_web_vitals",
        sa.Column("accessibility_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "core_web_vitals",
        sa.Column("best_practices_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "core_web_vitals", sa.Column("seo_score", sa.Float(), nullable=True)
    )
    op.add_column(
        "core_web_vitals",
        sa.Column("report_json", postgresql.JSONB(), nullable=True),
    )

    op.drop_column("core_web_vitals", "inp")
    op.drop_column("core_web_vitals", "inp_is_estimated")
    op.drop_column("core_web_vitals", "data_source")
    op.drop_column("core_web_vitals", "lcp_element")
    op.drop_column("core_web_vitals", "issues_json")


def downgrade() -> None:
    op.add_column(
        "core_web_vitals",
        sa.Column("issues_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "core_web_vitals",
        sa.Column("lcp_element", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "core_web_vitals",
        sa.Column(
            "data_source",
            sa.String(length=10),
            server_default="lab",
            nullable=False,
        ),
    )
    op.add_column(
        "core_web_vitals",
        sa.Column(
            "inp_is_estimated",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column("core_web_vitals", sa.Column("inp", sa.Float(), nullable=True))

    op.drop_column("core_web_vitals", "report_json")
    op.drop_column("core_web_vitals", "seo_score")
    op.drop_column("core_web_vitals", "best_practices_score")
    op.drop_column("core_web_vitals", "accessibility_score")
    op.drop_column("core_web_vitals", "field_inp")
    op.drop_column("core_web_vitals", "speed_index")
    op.drop_column("core_web_vitals", "tbt")
    op.drop_column("core_web_vitals", "fcp")
    op.drop_column("core_web_vitals", "strategy")
