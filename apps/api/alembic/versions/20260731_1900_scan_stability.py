"""Add scan-stability fields to core_web_vitals.

Records per-run values + the score/CLS spread across recent scans, and a
``high_variance`` flag so the UI/fix-verification can stop misattributing a
rotating carousel's natural score swings to an applied fix.

Revision ID: 0019_scan_stability
Revises: 0018_wp_transport
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0019_scan_stability"
down_revision: Union[str, None] = "0018_wp_transport"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "core_web_vitals",
        sa.Column("scan_run_details", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "core_web_vitals",
        sa.Column(
            "high_variance",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("core_web_vitals", "high_variance")
    op.drop_column("core_web_vitals", "scan_run_details")
