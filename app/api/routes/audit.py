from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import (
    AuditActorOptionRead,
    AuditEventPageRead,
    AuditEventRead,
    AuditStatsRead,
)
from app.services.audit import AuditService, AuditWorkspaceNotFoundError

router = APIRouter(tags=["audit"])

DbSession = Annotated[Session, Depends(get_db)]
SearchQuery = Annotated[str | None, Query(max_length=160)]
FilterCode = Annotated[str | None, Query(max_length=100)]
EntityIdFilter = Annotated[str | None, Query(max_length=160)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
LegacyLimit = Annotated[int, Query(ge=1, le=500)]
CanReadAudit = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("audit.read")),
]


def _event_read(view) -> AuditEventRead:
    return AuditEventRead(
        public_id=view.event.public_id,
        actor_type=view.event.actor_type,
        actor_user_public_id=view.actor_user_public_id,
        actor_user_name=view.actor_user_name,
        actor_role=view.actor_role,
        entity_type=view.event.entity_type,
        entity_public_id=view.event.entity_public_id,
        action=view.event.action,
        before_data=view.event.before_data,
        after_data=view.event.after_data,
        metadata=dict(view.event.metadata_json),
        created_at=view.event.created_at,
    )


@router.get(
    "/workspaces/{workspace_public_id}/audit",
    response_model=list[AuditEventRead],
)
def list_audit_events(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadAudit,
    entity_type: str | None = None,
    entity_public_id: str | None = None,
    action: str | None = None,
    limit: LegacyLimit = 100,
) -> list[AuditEventRead]:
    try:
        views = AuditService(db).list_events(
            workspace_public_id,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            action=action,
            limit=limit,
        )
    except AuditWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [_event_read(view) for view in views]


@router.get(
    "/workspaces/{workspace_public_id}/audit/search",
    response_model=AuditEventPageRead,
)
def search_audit_events(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadAudit,
    q: SearchQuery = None,
    actor_type: FilterCode = None,
    actor_user_public_id: FilterCode = None,
    entity_type: FilterCode = None,
    entity_public_id: EntityIdFilter = None,
    action: FilterCode = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 25,
) -> AuditEventPageRead:
    try:
        result = AuditService(db).search_events(
            workspace_public_id,
            query=q,
            actor_type=actor_type,
            actor_user_public_id=actor_user_public_id,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            action=action,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        )
    except AuditWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AuditEventPageRead(
        items=[_event_read(view) for view in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        stats=AuditStatsRead(
            total_events=result.total,
            user_events=result.actor_counts.get("user", 0),
            system_events=result.actor_counts.get("system", 0),
            atlas_events=result.actor_counts.get("atlas", 0),
            integration_events=result.actor_counts.get("integration", 0),
        ),
        available_actor_types=result.available_actor_types,
        available_entity_types=result.available_entity_types,
        available_actions=result.available_actions,
        available_actors=[
            AuditActorOptionRead(
                public_id=actor.public_id,
                name=actor.name,
                role=actor.role,
            )
            for actor in result.available_actors
        ],
    )
