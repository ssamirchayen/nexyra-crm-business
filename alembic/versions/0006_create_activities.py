"""create activities

Revision ID: 0006_create_activities
Revises: 0005_create_opportunities
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_create_activities"
down_revision: str | Sequence[str] | None = "0005_create_opportunities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
        sa.Column("owner_membership_id", sa.Integer(), nullable=True),
        sa.Column("activity_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["opportunities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_membership_id"],
            ["workspace_memberships.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )

    op.create_index(
        op.f("ix_activities_lead_id"),
        "activities",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activities_opportunity_id"),
        "activities",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activities_owner_membership_id"),
        "activities",
        ["owner_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activities_public_id"),
        "activities",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_activities_workspace_id"),
        "activities",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_activities_workspace_status_due",
        "activities",
        ["workspace_id", "status", "due_at"],
        unique=False,
    )
    op.create_index(
        "ix_activities_workspace_type",
        "activities",
        ["workspace_id", "activity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_activities_workspace_type",
        table_name="activities",
    )
    op.drop_index(
        "ix_activities_workspace_status_due",
        table_name="activities",
    )
    op.drop_index(
        op.f("ix_activities_workspace_id"),
        table_name="activities",
    )
    op.drop_index(
        op.f("ix_activities_public_id"),
        table_name="activities",
    )
    op.drop_index(
        op.f("ix_activities_owner_membership_id"),
        table_name="activities",
    )
    op.drop_index(
        op.f("ix_activities_opportunity_id"),
        table_name="activities",
    )
    op.drop_index(
        op.f("ix_activities_lead_id"),
        table_name="activities",
    )
    op.drop_table("activities")
