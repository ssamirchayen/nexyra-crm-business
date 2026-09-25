from __future__ import annotations

from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    ensure_can_assign_user,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import LeadCreate, LeadIntakeRead, LeadPageRead, LeadRead, LeadUpdate
from app.services import (
    LeadCustomFieldError,
    LeadDuplicateError,
    LeadNotFoundError,
    LeadOwnerError,
    LeadService,
    LeadStatusError,
    WorkspaceNotFoundError,
)

router = APIRouter(tags=["leads"])

DbSession = Annotated[Session, Depends(get_db)]
SearchQuery = Annotated[str | None, Query(max_length=160)]
FilterCode = Annotated[str | None, Query(max_length=160)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
CanReadLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.read")),
]
CanCreateLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.create")),
]
CanUpdateLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.update")),
]


def _serialize(view) -> LeadRead:
    lead = view.lead

    return LeadRead(
        public_id=lead.public_id,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        external_id=lead.external_id,
        interest=lead.interest,
        source=lead.source,
        channel=lead.channel,
        campaign=lead.campaign,
        message=lead.message,
        status=lead.status,
        priority=lead.priority,
        custom_fields=dict(lead.custom_fields),
        owner_user_public_id=view.owner_user_public_id,
        consent=lead.consent,
        active=lead.active,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _translate_error(exc: ValueError) -> None:
    if isinstance(exc, WorkspaceNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if isinstance(exc, LeadNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if isinstance(exc, LeadDuplicateError):
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "existing_lead_public_id": exc.lead_public_id,
            },
        ) from exc

    if isinstance(
        exc,
        (
            LeadOwnerError,
            LeadStatusError,
            LeadCustomFieldError,
        ),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    raise exc


@router.post(
    "/workspaces/{workspace_public_id}/leads",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
)
def create_lead(
    workspace_public_id: str,
    payload: LeadCreate,
    db: DbSession,
    authorization: CanCreateLeads,
) -> LeadRead:
    if payload.owner_user_public_id is not None:
        ensure_can_assign_user(authorization, payload.owner_user_public_id)

    try:
        view = LeadService(db).create(
            workspace_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.get(
    "/workspaces/{workspace_public_id}/leads",
    response_model=list[LeadRead],
)
def list_leads(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
) -> list[LeadRead]:
    try:
        views = LeadService(db).list_all(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise

    return [_serialize(view) for view in views]


@router.get(
    "/workspaces/{workspace_public_id}/leads/search",
    response_model=LeadPageRead,
)
def search_leads(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
    q: SearchQuery = None,
    lead_status: FilterCode = None,
    priority: FilterCode = None,
    source: FilterCode = None,
    channel: FilterCode = None,
    campaign: FilterCode = None,
    owner_user_public_id: FilterCode = None,
    unassigned: bool = False,
    active: bool | None = True,
    page: PageNumber = 1,
    page_size: PageSize = 20,
) -> LeadPageRead:
    try:
        result = LeadService(db).search(
            workspace_public_id,
            query=q,
            status=lead_status,
            priority=priority,
            source=source,
            channel=channel,
            campaign=campaign,
            owner_user_public_id=owner_user_public_id,
            only_unassigned=unassigned,
            active=active,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    total_pages = ceil(result.total / result.page_size) if result.total else 0

    return LeadPageRead(
        items=[_serialize(view) for view in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=total_pages,
    )


@router.get(
    "/workspaces/{workspace_public_id}/leads/{lead_public_id}",
    response_model=LeadRead,
)
def get_lead(
    workspace_public_id: str,
    lead_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
) -> LeadRead:
    try:
        view = LeadService(db).get(
            workspace_public_id,
            lead_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.patch(
    "/workspaces/{workspace_public_id}/leads/{lead_public_id}",
    response_model=LeadRead,
)
def update_lead(
    workspace_public_id: str,
    lead_public_id: str,
    payload: LeadUpdate,
    db: DbSession,
    authorization: CanUpdateLeads,
) -> LeadRead:
    if "owner_user_public_id" in payload.model_fields_set:
        ensure_can_assign_user(authorization, payload.owner_user_public_id)

    try:
        view = LeadService(db).update(
            workspace_public_id,
            lead_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.post(
    "/workspaces/{workspace_public_id}/leads/{lead_public_id}/deactivate",
    response_model=LeadRead,
)
def deactivate_lead(
    workspace_public_id: str,
    lead_public_id: str,
    db: DbSession,
    _authorization: CanUpdateLeads,
) -> LeadRead:
    try:
        view = LeadService(db).deactivate(
            workspace_public_id,
            lead_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.post(
    "/workspaces/{workspace_public_id}/leads/intake",
    response_model=LeadIntakeRead,
)
def intake_lead(
    workspace_public_id: str,
    payload: LeadCreate,
    db: DbSession,
    authorization: CanCreateLeads,
) -> LeadIntakeRead:
    if payload.owner_user_public_id is not None:
        ensure_can_assign_user(authorization, payload.owner_user_public_id)

    try:
        action, view = LeadService(db).intake(
            workspace_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return LeadIntakeRead(
        action=action,
        lead=_serialize(view),
    )
