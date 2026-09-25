"""create workspaces table

Revision ID: 0001_create_workspaces
Revises:
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_create_workspaces"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("segment", sa.String(length=50), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        op.f("ix_workspaces_public_id"),
        "workspaces",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_workspaces_slug"),
        "workspaces",
        ["slug"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workspaces_slug"),
        table_name="workspaces",
    )
    op.drop_index(
        op.f("ix_workspaces_public_id"),
        table_name="workspaces",
    )
    op.drop_table("workspaces")
