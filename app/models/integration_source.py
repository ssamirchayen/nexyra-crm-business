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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _integration_public_id() -> str:
    return f"INT-{uuid4().hex[:12].upper()}"


class IntegrationSource(Base):
    __tablename__ = "integration_sources"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "name",
            name="uq_integration_sources_workspace_name",
        ),
        Index(
            "ix_integration_sources_workspace_provider",
            "workspace_id",
            "provider",
        ),
        Index(
            "ix_integration_sources_workspace_source_channel",
            "workspace_id",
            "source",
            "channel",
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
        default=_integration_public_id,
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    channel: Mapped[str] = mapped_column(String(80), nullable=False)
    default_campaign: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    routing_config: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    provider_config: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
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
    intake_key_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    intake_key_prefix: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
    )
    intake_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_intake_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def external_intake_enabled(self) -> bool:
        return bool(self.intake_key_hash)
