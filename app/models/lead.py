from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _lead_public_id() -> str:
    return f"LEAD-{uuid4().hex[:12].upper()}"


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index(
            "ix_leads_workspace_phone",
            "workspace_id",
            "normalized_phone",
        ),
        Index(
            "ix_leads_workspace_email",
            "workspace_id",
            "normalized_email",
        ),
        Index(
            "ix_leads_workspace_external",
            "workspace_id",
            "external_id",
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
        default=_lead_public_id,
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    owner_membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_memberships.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    normalized_phone: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    external_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    interest: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="internet",
    )
    channel: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="web",
    )
    campaign: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="novo",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="media",
    )
    custom_fields: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
