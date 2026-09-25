from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil

from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.repositories import (
    AuditRepository,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)


@dataclass(frozen=True)
class AuditView:
    event: AuditEvent
    actor_user_public_id: str | None
    actor_user_name: str | None
    actor_role: str | None


@dataclass(frozen=True)
class AuditActorOptionView:
    public_id: str
    name: str
    role: str


@dataclass(frozen=True)
class AuditPageView:
    items: list[AuditView]
    total: int
    page: int
    page_size: int
    total_pages: int
    actor_counts: dict[str, int]
    available_actor_types: list[str]
    available_entity_types: list[str]
    available_actions: list[str]
    available_actors: list[AuditActorOptionView]


class AuditActorError(ValueError):
    pass


class AuditWorkspaceNotFoundError(ValueError):
    pass


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit = AuditRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise AuditWorkspaceNotFoundError(
                f"Empresa não encontrada: {public_id}"
            )
        return workspace

    def resolve_actor_membership_id(
        self,
        *,
        workspace_id: int,
        actor_user_public_id: str | None,
    ) -> int | None:
        if actor_user_public_id is None:
            return None

        user = self.users.get_by_public_id(actor_user_public_id)
        if user is None:
            raise AuditActorError(
                f"Ator não encontrado: {actor_user_public_id}"
            )

        membership = self.memberships.get(
            workspace_id=workspace_id,
            user_id=user.id,
        )

        if membership is None or not membership.active:
            raise AuditActorError(
                "O ator não possui acesso ativo a esta empresa."
            )

        return membership.id

    def record(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        entity_public_id: str,
        action: str,
        actor_type: str | None = None,
        actor_membership_id: int | None = None,
        before_data: dict[str, object] | None = None,
        after_data: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        resolved_actor_type = actor_type
        resolved_actor_membership_id = actor_membership_id

        if resolved_actor_type is None:
            resolved_actor_type = str(
                self.db.info.get("audit_actor_type", "system")
            )
            if resolved_actor_membership_id is None:
                stored_membership_id = self.db.info.get(
                    "audit_actor_membership_id"
                )
                if isinstance(stored_membership_id, int):
                    resolved_actor_membership_id = stored_membership_id

        return self.audit.create(
            workspace_id=workspace_id,
            actor_membership_id=resolved_actor_membership_id,
            actor_type=resolved_actor_type,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            action=action,
            before_data=before_data,
            after_data=after_data,
            metadata_json=dict(metadata or {}),
        )

    def list_events(
        self,
        workspace_public_id: str,
        *,
        entity_type: str | None = None,
        entity_public_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditView]:
        workspace = self._workspace(workspace_public_id)

        events = self.audit.list_for_workspace(
            workspace_id=workspace.id,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            action=action,
            limit=limit,
        )

        views: list[AuditView] = []
        for event in events:
            actor_public_id, actor_name, actor_role = self.audit.actor_details(
                event.actor_membership_id
            )
            views.append(
                AuditView(
                    event=event,
                    actor_user_public_id=actor_public_id,
                    actor_user_name=actor_name,
                    actor_role=actor_role,
                )
            )
        return views

    def search_events(
        self,
        workspace_public_id: str,
        *,
        query: str | None = None,
        actor_type: str | None = None,
        actor_user_public_id: str | None = None,
        entity_type: str | None = None,
        entity_public_id: str | None = None,
        action: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> AuditPageView:
        workspace = self._workspace(workspace_public_id)
        offset = (page - 1) * page_size

        rows, total, actor_counts = self.audit.search_for_workspace(
            workspace_id=workspace.id,
            query=query,
            actor_type=actor_type,
            actor_user_public_id=actor_user_public_id,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            action=action,
            created_from=created_from,
            created_to=created_to,
            offset=offset,
            limit=page_size,
        )

        actor_types, entity_types, actions = self.audit.facets_for_workspace(
            workspace_id=workspace.id
        )
        actor_options = [
            AuditActorOptionView(
                public_id=user.public_id,
                name=user.name,
                role=membership.role,
            )
            for membership, user in self.memberships.list_for_workspace(workspace.id)
        ]

        items = [
            AuditView(
                event=event,
                actor_user_public_id=actor_public_id,
                actor_user_name=actor_name,
                actor_role=actor_role,
            )
            for event, actor_public_id, actor_name, actor_role in rows
        ]

        total_pages = ceil(total / page_size) if total else 0
        return AuditPageView(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            actor_counts=actor_counts,
            available_actor_types=actor_types,
            available_entity_types=entity_types,
            available_actions=actions,
            available_actors=actor_options,
        )
