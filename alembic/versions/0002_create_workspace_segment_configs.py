"""create workspace segment configs

Revision ID: 0002_create_workspace_segment_configs
Revises: 0001_create_workspaces
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_create_workspace_segment_configs"
down_revision: str | Sequence[str] | None = "0001_create_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_segment_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("segment_code", sa.String(length=50), nullable=False),
        sa.Column("interest_label", sa.String(length=80), nullable=False),
        sa.Column("pipeline", sa.JSON(), nullable=False),
        sa.Column("custom_fields", sa.JSON(), nullable=False),
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
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        op.f("ix_workspace_segment_configs_workspace_id"),
        "workspace_segment_configs",
        ["workspace_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workspace_segment_configs_workspace_id"),
        table_name="workspace_segment_configs",
    )
    op.drop_table("workspace_segment_configs")
