"""create lead distribution configs

Revision ID: 0015_create_lead_distribution_configs
Revises: 0014_create_whatsapp_messages
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_create_lead_distribution_configs"
down_revision: str | Sequence[str] | None = "0014_create_whatsapp_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_distribution_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "strategy",
            sa.String(length=30),
            nullable=False,
            server_default="least_loaded",
        ),
        sa.Column("eligible_roles", sa.JSON(), nullable=False),
        sa.Column("eligible_user_public_ids", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("last_assigned_membership_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["last_assigned_membership_id"],
            ["workspace_memberships.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        "ix_lead_distribution_configs_workspace_id",
        "lead_distribution_configs",
        ["workspace_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lead_distribution_configs_workspace_id",
        table_name="lead_distribution_configs",
    )
    op.drop_table("lead_distribution_configs")
