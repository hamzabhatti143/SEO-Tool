"""Initial baseline schema.

Captures the complete current schema for RankPilot AI. The project was
developed against ``Base.metadata.create_all``; this migration establishes
the Alembic baseline so all future changes are versioned.

Tables: users, subscriptions, projects, audit_reports, keywords, content.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("now()")


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
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
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "plan", sa.String(length=20), server_default="free", nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- subscriptions (1:1 with users) ---
    op.create_table(
        "subscriptions",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tier", sa.String(length=20), server_default="free", nullable=False
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "current_period_end", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column(
            "stripe_subscription_id", sa.String(length=255), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True
    )

    # --- projects ---
    op.create_table(
        "projects",
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
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_projects_owner_id", "projects", ["owner_id"], unique=False
    )

    # --- audit_reports ---
    op.create_table(
        "audit_reports",
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
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("results", postgresql.JSONB(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_reports_project_id",
        "audit_reports",
        ["project_id"],
        unique=False,
    )

    # --- keywords ---
    op.create_table(
        "keywords",
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
        sa.Column("seed_keyword", sa.String(length=255), nullable=False),
        sa.Column("term", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.String(length=20),
            server_default="related",
            nullable=False,
        ),
        sa.Column("search_intent", sa.String(length=30), nullable=True),
        sa.Column("difficulty", sa.String(length=10), nullable=True),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("cluster_label", sa.String(length=120), nullable=True),
        sa.Column("trend_score", sa.Integer(), nullable=True),
        sa.Column("trend_direction", sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_keywords_project_id", "keywords", ["project_id"], unique=False
    )

    # --- content ---
    op.create_table(
        "content",
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
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("target_keyword", sa.String(length=255), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=30),
            server_default="blog",
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("meta_description", sa.String(length=320), nullable=True),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_project_id", "content", ["project_id"], unique=False
    )


def downgrade() -> None:
    # Drop in reverse dependency order. drop_table also drops its indexes.
    op.drop_table("content")
    op.drop_table("keywords")
    op.drop_table("audit_reports")
    op.drop_table("projects")
    op.drop_table("subscriptions")
    op.drop_table("users")
