"""Add white-label branding columns to projects.

Revision ID: 0004_project_branding
Revises: 0003_rank_tracking
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_project_branding"
down_revision: Union[str, None] = "0003_rank_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects", sa.Column("brand_name", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "projects",
        sa.Column("brand_logo_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "projects", sa.Column("brand_color", sa.String(length=9), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("projects", "brand_color")
    op.drop_column("projects", "brand_logo_url")
    op.drop_column("projects", "brand_name")
