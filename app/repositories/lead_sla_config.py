from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LeadSlaConfig


class LeadSlaConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_workspace_id(self, workspace_id: int) -> LeadSlaConfig | None:
        return self.db.scalar(
            select(LeadSlaConfig).where(
                LeadSlaConfig.workspace_id == workspace_id
            )
        )

    def create(self, **values: object) -> LeadSlaConfig:
        config = LeadSlaConfig(**values)
        self.db.add(config)
        self.db.flush()
        return config

    def save(self, config: LeadSlaConfig) -> LeadSlaConfig:
        self.db.add(config)
        self.db.flush()
        return config
