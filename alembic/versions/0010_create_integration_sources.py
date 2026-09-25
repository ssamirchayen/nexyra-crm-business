"""create integration sources

Revision ID: 0010_create_integration_sources
Revises: 0009_security_hardening
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_create_integration_sources"
down_revision: str | Sequence[str] | None = "0009_security_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("default_campaign", sa.String(length=160), nullable=True),
        sa.Column("routing_config", sa.JSON(), nullable=False),
        sa.Column("provider_config", sa.JSON(), nullable=False),
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
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "name",
            name="uq_integration_sources_workspace_name",
        ),
    )
    op.create_index(
        op.f("ix_integration_sources_public_id"),
        "integration_sources",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_integration_sources_workspace_id"),
        "integration_sources",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_integration_sources_workspace_provider",
        "integration_sources",
        ["workspace_id", "provider"],
        unique=False,
    )
    op.create_index(
        "ix_integration_sources_workspace_source_channel",
        "integration_sources",
        ["workspace_id", "source", "channel"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_sources_workspace_source_channel",
        table_name="integration_sources",
    )
    op.drop_index(
        "ix_integration_sources_workspace_provider",
        table_name="integration_sources",
    )
    op.drop_index(
        op.f("ix_integration_sources_workspace_id"),
        table_name="integration_sources",
    )
    op.drop_index(
        op.f("ix_integration_sources_public_id"),
        table_name="integration_sources",
    )
    op.drop_table("integration_sources")
