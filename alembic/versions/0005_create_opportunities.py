"""create opportunities and stage history

Revision ID: 0005_create_opportunities
Revises: 0004_create_leads
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_create_opportunities"
down_revision: str | Sequence[str] | None = "0004_create_leads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("owner_membership_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "value_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("loss_reason", sa.Text(), nullable=True),
        sa.Column(
            "won_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "lost_at",
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
        op.f("ix_opportunities_lead_id"),
        "opportunities",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_opportunities_owner_membership_id"),
        "opportunities",
        ["owner_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_opportunities_public_id"),
        "opportunities",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_opportunities_workspace_id"),
        "opportunities",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunities_workspace_stage",
        "opportunities",
        ["workspace_id", "stage"],
        unique=False,
    )
    op.create_index(
        "ix_opportunities_workspace_status",
        "opportunities",
        ["workspace_id", "status"],
        unique=False,
    )

    op.create_table(
        "opportunity_stage_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column(
            "changed_by_membership_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("from_stage", sa.String(length=80), nullable=True),
        sa.Column("to_stage", sa.String(length=80), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_membership_id"],
            ["workspace_memberships.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["opportunities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_opportunity_stage_history_opportunity_id"),
        "opportunity_stage_history",
        ["opportunity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_opportunity_stage_history_opportunity_id"),
        table_name="opportunity_stage_history",
    )
    op.drop_table("opportunity_stage_history")

    op.drop_index(
        "ix_opportunities_workspace_status",
        table_name="opportunities",
    )
    op.drop_index(
        "ix_opportunities_workspace_stage",
        table_name="opportunities",
    )
    op.drop_index(
        op.f("ix_opportunities_workspace_id"),
        table_name="opportunities",
    )
    op.drop_index(
        op.f("ix_opportunities_public_id"),
        table_name="opportunities",
    )
    op.drop_index(
        op.f("ix_opportunities_owner_membership_id"),
        table_name="opportunities",
    )
    op.drop_index(
        op.f("ix_opportunities_lead_id"),
        table_name="opportunities",
    )
    op.drop_table("opportunities")
