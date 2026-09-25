"""create leads

Revision ID: 0004_create_leads
Revises: 0003_create_users_and_memberships
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_create_leads"
down_revision: str | Sequence[str] | None = (
    "0003_create_users_and_memberships"
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("owner_membership_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("normalized_phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("normalized_email", sa.String(length=255), nullable=True),
        sa.Column("external_id", sa.String(length=160), nullable=True),
        sa.Column("interest", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("campaign", sa.String(length=160), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("custom_fields", sa.JSON(), nullable=False),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
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
        op.f("ix_leads_owner_membership_id"),
        "leads",
        ["owner_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leads_public_id"),
        "leads",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_leads_workspace_id"),
        "leads",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_leads_workspace_phone",
        "leads",
        ["workspace_id", "normalized_phone"],
        unique=False,
    )
    op.create_index(
        "ix_leads_workspace_email",
        "leads",
        ["workspace_id", "normalized_email"],
        unique=False,
    )
    op.create_index(
        "ix_leads_workspace_external",
        "leads",
        ["workspace_id", "external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_leads_workspace_external", table_name="leads")
    op.drop_index("ix_leads_workspace_email", table_name="leads")
    op.drop_index("ix_leads_workspace_phone", table_name="leads")
    op.drop_index(op.f("ix_leads_workspace_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_public_id"), table_name="leads")
    op.drop_index(
        op.f("ix_leads_owner_membership_id"),
        table_name="leads",
    )
    op.drop_table("leads")
