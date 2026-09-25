from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _audit_public_id() -> str:
    return f"AUD-{uuid4().hex[:12].upper()}"


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index(
            "ix_audit_workspace_entity",
            "workspace_id",
            "entity_type",
            "entity_public_id",
        ),
        Index(
            "ix_audit_workspace_action",
            "workspace_id",
            "action",
        ),
        Index(
            "ix_audit_workspace_created",
            "workspace_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    public_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        default=_audit_public_id,
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_memberships.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    actor_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="system",
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    entity_public_id: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    before_data: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    after_data: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
