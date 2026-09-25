"""create communication consent and policy tables

Revision ID: 0018_create_communication_consents
Revises: 0017_create_lead_cadences
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_create_communication_consents"
down_revision: str | Sequence[str] | None = "0017_create_lead_cadences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_communication_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "enforce_whatsapp_opt_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "enforce_email_opt_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "enforce_sms_opt_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "enforce_phone_opt_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "allow_legacy_lead_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "stop_cadence_on_block",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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
        sa.UniqueConstraint(
            "workspace_id",
            name="uq_workspace_communication_policies_workspace",
        ),
    )
    op.create_index(
        "ix_workspace_communication_policies_workspace_id",
        "workspace_communication_policies",
        ["workspace_id"],
    )

    op.create_table(
        "lead_communication_consents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("lawful_basis", sa.String(40), nullable=True),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "lead_id",
            "channel",
            name="uq_lead_communication_consents_lead_channel",
        ),
    )
    op.create_index(
        "ix_lead_communication_consents_public_id",
        "lead_communication_consents",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_lead_communication_consents_workspace_id",
        "lead_communication_consents",
        ["workspace_id"],
    )
    op.create_index(
        "ix_lead_communication_consents_lead_id",
        "lead_communication_consents",
        ["lead_id"],
    )
    op.create_index(
        "ix_lead_communication_consents_workspace_channel_status",
        "lead_communication_consents",
        ["workspace_id", "channel", "status"],
    )


def downgrade() -> None:
    op.drop_table("lead_communication_consents")
    op.drop_table("workspace_communication_policies")
