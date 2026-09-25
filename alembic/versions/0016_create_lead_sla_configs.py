"""create lead sla configs

Revision ID: 0016_create_lead_sla_configs
Revises: 0015_create_lead_distribution_configs
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_create_lead_sla_configs"
down_revision: str | Sequence[str] | None = "0015_create_lead_distribution_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_sla_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "first_response_minutes",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
        sa.Column(
            "warning_before_minutes",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "follow_up_due_hours",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
        sa.Column(
            "stale_lead_hours",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
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
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        "ix_lead_sla_configs_workspace_id",
        "lead_sla_configs",
        ["workspace_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lead_sla_configs_workspace_id",
        table_name="lead_sla_configs",
    )
    op.drop_table("lead_sla_configs")
