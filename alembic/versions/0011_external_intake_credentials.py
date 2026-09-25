"""external intake credentials

Revision ID: 0011_external_intake_credentials
Revises: 0010_create_integration_sources
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_external_intake_credentials"
down_revision: str | Sequence[str] | None = "0010_create_integration_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("integration_sources") as batch_op:
        batch_op.add_column(
            sa.Column("intake_key_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("intake_key_prefix", sa.String(length=24), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "intake_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_intake_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("integration_sources") as batch_op:
        batch_op.drop_column("last_intake_at")
        batch_op.drop_column("intake_count")
        batch_op.drop_column("intake_key_prefix")
        batch_op.drop_column("intake_key_hash")
