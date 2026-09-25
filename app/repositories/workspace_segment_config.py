from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkspaceSegmentConfig


class WorkspaceSegmentConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_workspace_id(
        self,
        workspace_id: int,
    ) -> WorkspaceSegmentConfig | None:
        statement = select(WorkspaceSegmentConfig).where(
            WorkspaceSegmentConfig.workspace_id == workspace_id
        )
        return self.db.scalar(statement)

    def save(
        self,
        config: WorkspaceSegmentConfig,
    ) -> WorkspaceSegmentConfig:
        self.db.add(config)
        self.db.flush()
        return config
