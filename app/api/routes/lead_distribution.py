from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import (
    LeadDistributionAssignmentRead,
    LeadDistributionConfigRead,
    LeadDistributionConfigUpdate,
    LeadDistributionMemberRead,
    LeadDistributionRunRead,
    LeadDistributionRunRequest,
    LeadDistributionSummaryRead,
)
from app.services.lead_distribution import (
    LeadDistributionConfigError,
    LeadDistributionService,
)
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["lead-distribution"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.read")),
]
CanAssignLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.assign")),
]


def _translate_error(exc: ValueError) -> None:
    if isinstance(exc, WorkspaceNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, LeadDistributionConfigError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


def _config_read(payload: LeadDistributionConfigUpdate) -> LeadDistributionConfigRead:
    return LeadDistributionConfigRead.model_validate(payload.model_dump())


@router.get(
    "/workspaces/{workspace_public_id}/lead-distribution/config",
    response_model=LeadDistributionConfigRead,
)
def get_distribution_config(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
) -> LeadDistributionConfigRead:
    try:
        payload = LeadDistributionService(db).get_config(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _config_read(payload)


@router.put(
    "/workspaces/{workspace_public_id}/lead-distribution/config",
    response_model=LeadDistributionConfigRead,
)
def update_distribution_config(
    workspace_public_id: str,
    payload: LeadDistributionConfigUpdate,
    db: DbSession,
    _authorization: CanAssignLeads,
) -> LeadDistributionConfigRead:
    try:
        saved = LeadDistributionService(db).save_config(
            workspace_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _config_read(saved)


@router.get(
    "/workspaces/{workspace_public_id}/lead-distribution/summary",
    response_model=LeadDistributionSummaryRead,
)
def distribution_summary(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
) -> LeadDistributionSummaryRead:
    try:
        summary = LeadDistributionService(db).summary(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise

    return LeadDistributionSummaryRead(
        config=_config_read(summary.config),
        members=[
            LeadDistributionMemberRead(
                user_public_id=item.user.public_id,
                name=item.user.name,
                role=item.membership.role,
                active=item.membership.active and item.user.active,
                eligible=item.eligible,
                assigned_active_leads=item.assigned_active_leads,
            )
            for item in summary.members
        ],
        unassigned_active_leads=summary.unassigned_active_leads,
        total_active_leads=summary.total_active_leads,
    )


@router.post(
    "/workspaces/{workspace_public_id}/lead-distribution/run",
    response_model=LeadDistributionRunRead,
)
def run_distribution(
    workspace_public_id: str,
    payload: LeadDistributionRunRequest,
    db: DbSession,
    _authorization: CanAssignLeads,
) -> LeadDistributionRunRead:
    try:
        result = LeadDistributionService(db).run(
            workspace_public_id,
            limit=payload.limit,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return LeadDistributionRunRead(
        dry_run=result.dry_run,
        scanned=result.scanned,
        assigned=result.assigned,
        skipped=result.skipped,
        assignments=[
            LeadDistributionAssignmentRead(
                lead_public_id=item.lead_public_id,
                user_public_id=item.user_public_id,
                user_name=item.user_name,
                strategy=item.strategy,
                rule_name=item.rule_name,
                previous_load=item.previous_load,
            )
            for item in result.assignments
        ],
    )
