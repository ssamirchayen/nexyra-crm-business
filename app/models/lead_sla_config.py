from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadSlaConfig(Base):
    __tablename__ = "lead_sla_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_response_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=15,
    )
    warning_before_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    follow_up_due_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
    )
    stale_lead_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
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
