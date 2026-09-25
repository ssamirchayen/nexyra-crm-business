from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    ensure_permission,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas.lead_batch import (
    LeadBatchItemRead,
    LeadBatchRequest,
    LeadBatchResultRead,
)
from app.services.lead import LeadNotFoundError, LeadOwnerError, LeadStatusError
from app.services.lead_batch import LeadBatchService
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["lead-batch"])

DbSession = Annotated[Session, Depends(get_db)]
CanUpdateLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.update")),
]


def _translate_error(exc: ValueError) -> None:
    if isinstance(exc, (WorkspaceNotFoundError, LeadNotFoundError)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (LeadOwnerError, LeadStatusError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.post(
    "/workspaces/{workspace_public_id}/leads/batch",
    response_model=LeadBatchResultRead,
)
def run_lead_batch(
    workspace_public_id: str,
    payload: LeadBatchRequest,
    db: DbSession,
    authorization: CanUpdateLeads,
) -> LeadBatchResultRead:
    if payload.owner_mode != "keep":
        ensure_permission(authorization, "leads.assign")

    try:
        result = LeadBatchService(db).run(workspace_public_id, payload)
    except ValueError as exc:
        _translate_error(exc)
        raise

    return LeadBatchResultRead(
        dry_run=result.dry_run,
        requested=result.requested,
        found=result.found,
        changed=result.changed,
        unchanged=result.unchanged,
        items=[LeadBatchItemRead(**item.__dict__) for item in result.items],
    )
