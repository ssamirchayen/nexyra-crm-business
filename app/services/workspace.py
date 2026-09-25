from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import workspace_snapshot
from app.models import Workspace
from app.repositories import WorkspaceMembershipRepository, WorkspaceRepository
from app.schemas import WorkspaceCreate, WorkspaceUpdate
from app.services.audit import AuditService


class WorkspaceNotFoundError(ValueError):
    pass


class WorkspaceSlugConflictError(ValueError):
    pass


class WorkspaceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = WorkspaceRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.audit = AuditService(db)

    def create(
        self,
        payload: WorkspaceCreate,
        *,
        creator_user_id: int | None = None,
    ) -> Workspace:
        if self.repository.get_by_slug(payload.slug) is not None:
            raise WorkspaceSlugConflictError(
                f"Já existe uma empresa com o slug '{payload.slug}'."
            )

        workspace = self.repository.create(
            name=payload.name,
            slug=payload.slug,
            segment=payload.segment,
        )

        creator_membership = None
        if creator_user_id is not None:
            creator_membership = self.memberships.create(
                workspace_id=workspace.id,
                user_id=creator_user_id,
                role="admin",
            )

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="workspace",
            entity_public_id=workspace.public_id,
            action="workspace.created",
            actor_type=("user" if creator_membership is not None else None),
            actor_membership_id=(
                creator_membership.id if creator_membership is not None else None
            ),
            after_data=workspace_snapshot(workspace),
        )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise WorkspaceSlugConflictError(
                f"Já existe uma empresa com o slug '{payload.slug}'."
            ) from exc

        self.db.refresh(workspace)
        return workspace

    def list_all(self) -> list[Workspace]:
        return self.repository.list_all()

    def get(self, public_id: str) -> Workspace:
        workspace = self.repository.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {public_id}"
            )
        return workspace

    def update(
        self,
        public_id: str,
        payload: WorkspaceUpdate,
    ) -> Workspace:
        workspace = self.get(public_id)
        before_data = workspace_snapshot(workspace)
        changes = payload.model_dump(exclude_unset=True)

        new_slug = changes.get("slug")
        if new_slug and new_slug != workspace.slug:
            existing = self.repository.get_by_slug(new_slug)
            if existing is not None and existing.public_id != public_id:
                raise WorkspaceSlugConflictError(
                    f"Já existe uma empresa com o slug '{new_slug}'."
                )

        for field_name, value in changes.items():
            setattr(workspace, field_name, value)

        self.repository.save(workspace)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="workspace",
            entity_public_id=workspace.public_id,
            action="workspace.updated",
            before_data=before_data,
            after_data=workspace_snapshot(workspace),
        )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise WorkspaceSlugConflictError(
                "Não foi possível atualizar a empresa por conflito de dados."
            ) from exc

        self.db.refresh(workspace)
        return workspace

    def deactivate(self, public_id: str) -> Workspace:
        workspace = self.get(public_id)
        before_data = workspace_snapshot(workspace)

        workspace.active = False
        self.repository.save(workspace)

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="workspace",
            entity_public_id=workspace.public_id,
            action="workspace.deactivated",
            before_data=before_data,
            after_data=workspace_snapshot(workspace),
        )

        self.db.commit()
        self.db.refresh(workspace)
        return workspace
