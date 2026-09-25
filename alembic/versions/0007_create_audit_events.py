"""create audit events

Revision ID: 0007_create_audit_events
Revises: 0006_create_activities
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_create_audit_events"
down_revision: str | Sequence[str] | None = "0006_create_activities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("actor_membership_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_public_id", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_membership_id"],
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
        op.f("ix_audit_events_actor_membership_id"),
        "audit_events",
        ["actor_membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_public_id"),
        "audit_events",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_audit_events_workspace_id"),
        "audit_events",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_workspace_action",
        "audit_events",
        ["workspace_id", "action"],
        unique=False,
    )
    op.create_index(
        "ix_audit_workspace_created",
        "audit_events",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_workspace_entity",
        "audit_events",
        ["workspace_id", "entity_type", "entity_public_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_workspace_entity",
        table_name="audit_events",
    )
    op.drop_index(
        "ix_audit_workspace_created",
        table_name="audit_events",
    )
    op.drop_index(
        "ix_audit_workspace_action",
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_workspace_id"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_public_id"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_actor_membership_id"),
        table_name="audit_events",
    )
    op.drop_table("audit_events")
