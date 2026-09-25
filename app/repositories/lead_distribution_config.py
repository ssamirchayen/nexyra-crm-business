from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LeadDistributionConfig


class LeadDistributionConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_workspace_id(
        self,
        workspace_id: int,
    ) -> LeadDistributionConfig | None:
        statement = select(LeadDistributionConfig).where(
            LeadDistributionConfig.workspace_id == workspace_id
        )
        return self.db.scalar(statement)

    def create(self, **values: object) -> LeadDistributionConfig:
        config = LeadDistributionConfig(**values)
        self.db.add(config)
        self.db.flush()
        return config

    def save(self, config: LeadDistributionConfig) -> LeadDistributionConfig:
        self.db.add(config)
        self.db.flush()
        return config
