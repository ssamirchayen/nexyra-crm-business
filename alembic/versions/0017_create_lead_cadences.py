"""create lead cadences

Revision ID: 0017_create_lead_cadences
Revises: 0016_create_lead_sla_configs
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_create_lead_cadences"
down_revision: str | Sequence[str] | None = "0016_create_lead_sla_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_cadences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("stop_on_reply", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("ix_lead_cadences_public_id", "lead_cadences", ["public_id"], unique=True)
    op.create_index("ix_lead_cadences_workspace_id", "lead_cadences", ["workspace_id"])
    op.create_index("ix_lead_cadences_workspace_active", "lead_cadences", ["workspace_id", "active"])

    op.create_table(
        "lead_cadence_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cadence_id", sa.Integer(), sa.ForeignKey("lead_cadences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lead_cadence_steps_cadence_id", "lead_cadence_steps", ["cadence_id"])
    op.create_index("ix_lead_cadence_steps_cadence_position", "lead_cadence_steps", ["cadence_id", "position"], unique=True)

    op.create_table(
        "lead_cadence_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cadence_id", sa.Integer(), sa.ForeignKey("lead_cadences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("ix_lead_cadence_enrollments_public_id", "lead_cadence_enrollments", ["public_id"], unique=True)
    op.create_index("ix_lead_cadence_enrollments_workspace_id", "lead_cadence_enrollments", ["workspace_id"])
    op.create_index("ix_lead_cadence_enrollments_cadence_id", "lead_cadence_enrollments", ["cadence_id"])
    op.create_index("ix_lead_cadence_enrollments_lead_id", "lead_cadence_enrollments", ["lead_id"])
    op.create_index("ix_cadence_enrollments_workspace_status_next", "lead_cadence_enrollments", ["workspace_id", "status", "next_run_at"])
    op.create_index("ix_cadence_enrollments_lead_status", "lead_cadence_enrollments", ["lead_id", "status"])


def downgrade() -> None:
    op.drop_table("lead_cadence_enrollments")
    op.drop_table("lead_cadence_steps")
    op.drop_table("lead_cadences")
