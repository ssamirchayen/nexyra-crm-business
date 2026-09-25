"""security hardening

Revision ID: 0009_security_hardening
Revises: 0008_create_auth_foundation
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_security_hardening"
down_revision: str | Sequence[str] | None = "0008_create_auth_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_credentials") as batch_op:
        batch_op.add_column(
            sa.Column(
                "failed_login_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "last_failed_login_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    with op.batch_alter_table("auth_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("ip_address", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("user_agent", sa.String(length=512), nullable=True)
        )
        batch_op.add_column(
            sa.Column("revoked_reason", sa.String(length=80), nullable=True)
        )

    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_password_reset_requests_expires_at"),
        "password_reset_requests",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_requests_public_id"),
        "password_reset_requests",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_password_reset_requests_token_hash"),
        "password_reset_requests",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_password_reset_requests_user_id"),
        "password_reset_requests",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_password_reset_requests_user_id"),
        table_name="password_reset_requests",
    )
    op.drop_index(
        op.f("ix_password_reset_requests_token_hash"),
        table_name="password_reset_requests",
    )
    op.drop_index(
        op.f("ix_password_reset_requests_public_id"),
        table_name="password_reset_requests",
    )
    op.drop_index(
        op.f("ix_password_reset_requests_expires_at"),
        table_name="password_reset_requests",
    )
    op.drop_table("password_reset_requests")

    with op.batch_alter_table("auth_sessions") as batch_op:
        batch_op.drop_column("revoked_reason")
        batch_op.drop_column("user_agent")
        batch_op.drop_column("ip_address")

    with op.batch_alter_table("user_credentials") as batch_op:
        batch_op.drop_column("last_failed_login_at")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_attempts")
