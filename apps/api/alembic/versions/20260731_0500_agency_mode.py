"""Agency Mode: team members, invites, client share links, custom domain.

Revision ID: 0006_agency_mode
Revises: 0005_automation_settings
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_agency_mode"
down_revision: Union[str, None] = "0005_automation_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")
_FALSE = sa.text("false")


def _base_cols() -> list[sa.Column]:
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
    ]


def upgrade() -> None:
    op.add_column(
        "projects", sa.Column("custom_domain", sa.String(length=253), nullable=True)
    )

    op.create_table(
        "project_members",
        *_base_cols(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role", sa.String(length=20), server_default="viewer", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "user_id", name="uq_project_members_project_user"
        ),
    )
    op.create_index(
        "ix_project_members_project_id", "project_members", ["project_id"]
    )
    op.create_index(
        "ix_project_members_user_id", "project_members", ["user_id"]
    )

    op.create_table(
        "project_invites",
        *_base_cols(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "role", sa.String(length=20), server_default="viewer", nullable=False
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("accepted", sa.Boolean(), server_default=_FALSE, nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_invites_project_id", "project_invites", ["project_id"]
    )
    op.create_index(
        "ix_project_invites_token", "project_invites", ["token"], unique=True
    )

    op.create_table(
        "client_share_links",
        *_base_cols(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("revoked", sa.Boolean(), server_default=_FALSE, nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_client_share_links_project_id",
        "client_share_links",
        ["project_id"],
    )
    op.create_index(
        "ix_client_share_links_token",
        "client_share_links",
        ["token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("client_share_links")
    op.drop_table("project_invites")
    op.drop_table("project_members")
    op.drop_column("projects", "custom_domain")
