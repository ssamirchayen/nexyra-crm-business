from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Workspace


class WorkspaceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, name: str, slug: str, segment: str) -> Workspace:
        workspace = Workspace(name=name, slug=slug, segment=segment)
        self.db.add(workspace)
        self.db.flush()
        return workspace

    def list_all(self) -> list[Workspace]:
        statement = select(Workspace).order_by(Workspace.id.asc())
        return list(self.db.scalars(statement).all())

    def get_by_id(self, workspace_id: int) -> Workspace | None:
        statement = select(Workspace).where(Workspace.id == workspace_id)
        return self.db.scalar(statement)

    def get_by_public_id(self, public_id: str) -> Workspace | None:
        statement = select(Workspace).where(Workspace.public_id == public_id)
        return self.db.scalar(statement)

    def get_by_slug(self, slug: str) -> Workspace | None:
        statement = select(Workspace).where(Workspace.slug == slug)
        return self.db.scalar(statement)

    def save(self, workspace: Workspace) -> Workspace:
        self.db.add(workspace)
        self.db.flush()
        return workspace
