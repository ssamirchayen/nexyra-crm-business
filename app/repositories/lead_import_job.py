from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LeadImportJob


class LeadImportJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        workspace_id: int,
        integration_source_id: int | None,
        filename: str,
        delimiter: str,
        duplicate_mode: str,
        source: str,
        channel: str,
        campaign: str | None,
        field_mapping: dict[str, object],
        total_rows: int,
    ) -> LeadImportJob:
        job = LeadImportJob(
            workspace_id=workspace_id,
            integration_source_id=integration_source_id,
            filename=filename,
            delimiter=delimiter,
            duplicate_mode=duplicate_mode,
            source=source,
            channel=channel,
            campaign=campaign,
            field_mapping=field_mapping,
            total_rows=total_rows,
            status="processing",
        )
        self.db.add(job)
        self.db.flush()
        return job

    def save(self, job: LeadImportJob) -> LeadImportJob:
        self.db.add(job)
        self.db.flush()
        return job

    def list_recent(self, workspace_id: int, *, limit: int = 20) -> list[LeadImportJob]:
        statement = (
            select(LeadImportJob)
            .where(LeadImportJob.workspace_id == workspace_id)
            .order_by(LeadImportJob.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())
