from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMembership


class WorkspaceMembershipRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, *, workspace_id: int, user_id: int) -> WorkspaceMembership | None:
        statement = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        return self.db.scalar(statement)

    def list_for_workspace(
        self,
        workspace_id: int,
    ) -> list[tuple[WorkspaceMembership, User]]:
        statement = (
            select(WorkspaceMembership, User)
            .join(User, User.id == WorkspaceMembership.user_id)
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .order_by(WorkspaceMembership.id.asc())
        )
        return list(self.db.execute(statement).all())


    def list_for_user(
        self,
        user_id: int,
    ) -> list[tuple[WorkspaceMembership, Workspace]]:
        statement = (
            select(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(WorkspaceMembership.id.asc())
        )
        return list(self.db.execute(statement).all())

    def create(
        self,
        *,
        workspace_id: int,
        user_id: int,
        role: str,
    ) -> WorkspaceMembership:
        membership = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    def save(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        self.db.add(membership)
        self.db.flush()
        return membership
