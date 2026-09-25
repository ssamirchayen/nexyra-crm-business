from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OpportunityStageHistory(Base):
    __tablename__ = "opportunity_stage_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    changed_by_membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )

    from_stage: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )
    to_stage: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
