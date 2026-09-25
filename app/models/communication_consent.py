from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _consent_public_id() -> str:
    return f"CNS-{uuid4().hex[:12].upper()}"


class WorkspaceCommunicationPolicy(Base):
    __tablename__ = "workspace_communication_policies"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            name="uq_workspace_communication_policies_workspace",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    enforce_whatsapp_opt_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    enforce_email_opt_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    enforce_sms_opt_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    enforce_phone_opt_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    allow_legacy_lead_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    stop_cadence_on_block: Mapped[bool] = mapped_column(
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


class LeadCommunicationConsent(Base):
    __tablename__ = "lead_communication_consents"
    __table_args__ = (
        UniqueConstraint(
            "lead_id",
            "channel",
            name="uq_lead_communication_consents_lead_channel",
        ),
        Index(
            "ix_lead_communication_consents_workspace_channel_status",
            "workspace_id",
            "channel",
            "status",
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
        default=_consent_public_id,
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
    )
    lawful_basis: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )
    source: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )
    evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
