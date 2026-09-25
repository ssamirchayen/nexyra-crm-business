"""create integration secrets

Revision ID: 0013_create_integration_secrets
Revises: 0012_create_lead_import_jobs
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_create_integration_secrets"
down_revision: str | Sequence[str] | None = "0012_create_lead_import_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_secrets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("integration_source_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
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
            ["integration_source_id"],
            ["integration_sources.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("integration_source_id"),
    )
    op.create_index(
        "ix_integration_secrets_integration_source_id",
        "integration_secrets",
        ["integration_source_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_secrets_integration_source_id",
        table_name="integration_secrets",
    )
    op.drop_table("integration_secrets")
