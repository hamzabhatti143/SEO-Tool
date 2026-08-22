"""Add project.platform + credentials (platform connector system).

Revision ID: 0008_platform_connectors
Revises: 0007_core_web_vitals
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_platform_connectors"
down_revision: Union[str, None] = "0007_core_web_vitals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "platform",
            sa.String(length=20),
            server_default="custom",
            nullable=False,
        ),
    )

    op.create_table(
        "credentials",
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
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("encrypted_api_key_or_token", sa.Text(), nullable=False),
        sa.Column("site_url", sa.String(length=2048), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="connected",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_credentials_project_id"),
    )
    op.create_index(
        "ix_credentials_project_id",
        "credentials",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_credentials_project_id", table_name="credentials")
    op.drop_table("credentials")
    op.drop_column("projects", "platform")
