from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import (
    LeadSlaConfigRead,
    LeadSlaConfigUpdate,
    LeadSlaQueueItemRead,
    LeadSlaQueueMetricsRead,
    LeadSlaQueueRead,
)
from app.services.lead_sla import LeadSlaConfigError, LeadSlaService
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["lead-sla"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.read")),
]
CanUpdateSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.update")),
]
OwnerFilter = Annotated[str | None, Query(max_length=64)]
QueueLimit = Annotated[int, Query(ge=1, le=500)]


def _translate_error(exc: ValueError) -> None:
    if isinstance(exc, WorkspaceNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, LeadSlaConfigError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


def _config_read(payload: LeadSlaConfigUpdate) -> LeadSlaConfigRead:
    return LeadSlaConfigRead.model_validate(payload.model_dump())


@router.get(
    "/workspaces/{workspace_public_id}/lead-sla/config",
    response_model=LeadSlaConfigRead,
)
def get_sla_config(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
) -> LeadSlaConfigRead:
    try:
        payload = LeadSlaService(db).get_config(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _config_read(payload)


@router.put(
    "/workspaces/{workspace_public_id}/lead-sla/config",
    response_model=LeadSlaConfigRead,
)
def update_sla_config(
    workspace_public_id: str,
    payload: LeadSlaConfigUpdate,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> LeadSlaConfigRead:
    try:
        saved = LeadSlaService(db).save_config(workspace_public_id, payload)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _config_read(saved)


@router.get(
    "/workspaces/{workspace_public_id}/lead-sla/queue",
    response_model=LeadSlaQueueRead,
)
def get_sla_queue(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
    owner_user_public_id: OwnerFilter = None,
    unassigned: bool = False,
    limit: QueueLimit = 100,
) -> LeadSlaQueueRead:
    try:
        result = LeadSlaService(db).queue(
            workspace_public_id,
            owner_user_public_id=owner_user_public_id,
            only_unassigned=unassigned,
            limit=limit,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return LeadSlaQueueRead(
        config=_config_read(result.config),
        metrics=LeadSlaQueueMetricsRead(**result.metrics.__dict__),
        items=[
            LeadSlaQueueItemRead(
                lead_public_id=item.lead.public_id,
                lead_name=item.lead.name,
                phone=item.lead.phone,
                interest=item.lead.interest,
                status=item.lead.status,
                priority=item.lead.priority,
                source=item.lead.source,
                owner_user_public_id=item.owner_user_public_id,
                owner_name=item.owner_name,
                created_at=item.lead.created_at,
                age_minutes=item.age_minutes,
                first_contact_at=item.first_contact_at,
                first_response_minutes=item.first_response_minutes,
                sla_due_at=item.sla_due_at,
                sla_state=item.sla_state,
                last_contact_at=item.last_contact_at,
                pending_followups=item.pending_followups,
                overdue_followups=item.overdue_followups,
                next_followup_due_at=item.next_followup_due_at,
                stale=item.stale,
                score=item.score,
                reasons=item.reasons,
            )
            for item in result.items
        ],
    )
