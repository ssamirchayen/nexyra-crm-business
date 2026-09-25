"""create lead import jobs

Revision ID: 0012_create_lead_import_jobs
Revises: 0011_external_intake_credentials
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_create_lead_import_jobs"
down_revision: str | Sequence[str] | None = "0011_external_intake_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("integration_source_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("delimiter", sa.String(length=12), nullable=False),
        sa.Column("duplicate_mode", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("campaign", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("field_mapping", sa.JSON(), nullable=False),
        sa.Column("error_samples", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["integration_source_id"],
            ["integration_sources.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index(
        "ix_lead_import_jobs_public_id",
        "lead_import_jobs",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_lead_import_jobs_workspace_id",
        "lead_import_jobs",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_lead_import_jobs_integration_source_id",
        "lead_import_jobs",
        ["integration_source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lead_import_jobs_integration_source_id",
        table_name="lead_import_jobs",
    )
    op.drop_index("ix_lead_import_jobs_workspace_id", table_name="lead_import_jobs")
    op.drop_index("ix_lead_import_jobs_public_id", table_name="lead_import_jobs")
    op.drop_table("lead_import_jobs")
