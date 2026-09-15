"""Add credentials.wp_transport (WordPress REST vs admin-ajax fallback).

Records which transport verified the WordPress connection so every later
plugin call (snapshot / apply-fix / revert) uses the same channel:
  * "rest" — {site}/wp-json/{ns}/{action} with a Bearer header
  * "ajax" — {site}/wp-admin/admin-ajax.php?action=rankpilot_{action} with the
    key as a request parameter (for hosts that don't route /wp-json/).

Revision ID: 0018_wp_transport
Revises: 0017_technical_seo_issues
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_wp_transport"
down_revision: Union[str, None] = "0017_technical_seo_issues"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "credentials",
        sa.Column("wp_transport", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("credentials", "wp_transport")
