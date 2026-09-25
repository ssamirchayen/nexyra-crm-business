"""create whatsapp messages

Revision ID: 0014_create_whatsapp_messages
Revises: 0013_create_integration_secrets
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_create_whatsapp_messages"
down_revision: str | Sequence[str] | None = "0013_create_integration_secrets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("integration_source_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=180), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("from_phone", sa.String(length=40), nullable=True),
        sa.Column("to_phone", sa.String(length=40), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
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
            ["integration_source_id"],
            ["integration_sources.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("provider_message_id"),
    )
    op.create_index(
        "ix_whatsapp_messages_public_id",
        "whatsapp_messages",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_whatsapp_messages_workspace_id",
        "whatsapp_messages",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_integration_source_id",
        "whatsapp_messages",
        ["integration_source_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_lead_id",
        "whatsapp_messages",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_provider_message_id",
        "whatsapp_messages",
        ["provider_message_id"],
        unique=True,
    )
    op.create_index(
        "ix_whatsapp_messages_workspace_created",
        "whatsapp_messages",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_source_created",
        "whatsapp_messages",
        ["integration_source_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_messages_lead_created",
        "whatsapp_messages",
        ["lead_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_messages_lead_created", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_source_created", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_workspace_created", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_provider_message_id", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_lead_id", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_integration_source_id", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_workspace_id", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_public_id", table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
