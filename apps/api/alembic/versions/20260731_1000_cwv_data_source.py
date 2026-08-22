"""Add core_web_vitals.data_source (field vs lab, PageSpeed Insights).

Revision ID: 0010_cwv_data_source
Revises: 0009_change_log
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_cwv_data_source"
down_revision: Union[str, None] = "0009_change_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "core_web_vitals",
        sa.Column(
            "data_source",
            sa.String(length=10),
            server_default="lab",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("core_web_vitals", "data_source")
