from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    ensure_can_assign_user,
    require_workspace_permission,
)
from app.db import get_db
from app.integrations.external_intake import (
    ExternalIntakePayloadError,
    build_external_lead_payload,
)
from app.schemas import LeadCreate, LeadIntakeRead, LeadRead
from app.schemas.integration import (
    ExternalLeadIntakeRead,
    IntegrationCredentialRead,
    IntegrationOverviewRead,
    IntegrationProviderRead,
    IntegrationSourceCreate,
    IntegrationSourceRead,
    IntegrationSourceUpdate,
)
from app.services import (
    LeadCustomFieldError,
    LeadOwnerError,
    LeadService,
    LeadStatusError,
)
from app.services.integration import (
    ExternalIntakeCredentialError,
    ExternalIntakeUnsupportedError,
    IntegrationProviderError,
    IntegrationService,
    IntegrationSourceConflictError,
    IntegrationSourceInactiveError,
    IntegrationSourceNotFoundError,
    IntegrationWorkspaceNotFoundError,
)

router = APIRouter(tags=["integrations"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.read")),
]
CanUpdateSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.update")),
]
CanCreateLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.create")),
]


def _translate_error(exc: ValueError) -> None:
    if isinstance(
        exc,
        (IntegrationWorkspaceNotFoundError, IntegrationSourceNotFoundError),
    ):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ExternalIntakeCredentialError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(
        exc,
        (IntegrationSourceConflictError, IntegrationSourceInactiveError),
    ):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            ExternalIntakePayloadError,
            ExternalIntakeUnsupportedError,
            IntegrationProviderError,
            LeadCustomFieldError,
            LeadOwnerError,
            LeadStatusError,
        ),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


def _provider_read(item) -> IntegrationProviderRead:
    return IntegrationProviderRead(
        code=item.code,
        label=item.label,
        description=item.description,
        category=item.category,
        availability=item.availability,
        default_source=item.default_source,
        default_channel=item.default_channel,
        supports_multiple=item.supports_multiple,
        capabilities=list(item.capabilities),
    )


def _lead_read(view) -> LeadRead:
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


@router.get(
    "/workspaces/{workspace_public_id}/integrations/overview",
    response_model=IntegrationOverviewRead,
)
def integration_overview(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
) -> IntegrationOverviewRead:
    service = IntegrationService(db)
    try:
        sources = service.list_sources(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise

    return IntegrationOverviewRead(
        providers=[_provider_read(item) for item in service.catalog()],
        sources=[IntegrationSourceRead.model_validate(item) for item in sources],
        active_sources=sum(1 for item in sources if item.active),
        intake_endpoint=f"/workspaces/{workspace_public_id}/leads/intake",
    )


@router.get(
    "/workspaces/{workspace_public_id}/integrations/catalog",
    response_model=list[IntegrationProviderRead],
)
def integration_catalog(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
) -> list[IntegrationProviderRead]:
    service = IntegrationService(db)
    try:
        service.list_sources(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [_provider_read(item) for item in service.catalog()]


@router.get(
    "/workspaces/{workspace_public_id}/integrations",
    response_model=list[IntegrationSourceRead],
)
def list_integrations(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
) -> list[IntegrationSourceRead]:
    try:
        items = IntegrationService(db).list_sources(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [IntegrationSourceRead.model_validate(item) for item in items]


@router.post(
    "/workspaces/{workspace_public_id}/integrations",
    response_model=IntegrationSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_integration(
    workspace_public_id: str,
    payload: IntegrationSourceCreate,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> IntegrationSourceRead:
    try:
        item = IntegrationService(db).create_source(workspace_public_id, payload)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return IntegrationSourceRead.model_validate(item)


@router.patch(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}",
    response_model=IntegrationSourceRead,
)
def update_integration(
    workspace_public_id: str,
    integration_public_id: str,
    payload: IntegrationSourceUpdate,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> IntegrationSourceRead:
    try:
        item = IntegrationService(db).update_source(
            workspace_public_id,
            integration_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return IntegrationSourceRead.model_validate(item)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/intake",
    response_model=LeadIntakeRead,
)
def integration_intake(
    workspace_public_id: str,
    integration_public_id: str,
    payload: LeadCreate,
    db: DbSession,
    authorization: CanCreateLeads,
) -> LeadIntakeRead:
    service = IntegrationService(db)
    try:
        source = service.require_active_source(
            workspace_public_id,
            integration_public_id,
        )
        normalized_payload = payload.model_copy(
            update={
                "source": source.source,
                "channel": source.channel,
                "campaign": payload.campaign or source.default_campaign,
            }
        )
        if normalized_payload.owner_user_public_id is not None:
            ensure_can_assign_user(
                authorization,
                normalized_payload.owner_user_public_id,
            )
        action, view = LeadService(db).intake(
            workspace_public_id,
            normalized_payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return LeadIntakeRead(action=action, lead=_lead_read(view))


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/external-key/rotate",
    response_model=IntegrationCredentialRead,
)
def rotate_external_key(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> IntegrationCredentialRead:
    try:
        item, raw_key = IntegrationService(db).rotate_external_intake_key(
            workspace_public_id,
            integration_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return IntegrationCredentialRead(
        integration_public_id=item.public_id,
        intake_key=raw_key,
        key_prefix=item.intake_key_prefix or "",
        intake_endpoint=f"/external/integrations/{item.public_id}/intake",
    )


@router.delete(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/external-key",
    response_model=IntegrationSourceRead,
)
def revoke_external_key(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> IntegrationSourceRead:
    try:
        item = IntegrationService(db).revoke_external_intake_key(
            workspace_public_id,
            integration_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return IntegrationSourceRead.model_validate(item)


@router.post(
    "/external/integrations/{integration_public_id}/intake",
    response_model=ExternalLeadIntakeRead,
    name="external_integration_intake",
)
def external_integration_intake(
    integration_public_id: str,
    payload: dict[str, Any],
    request: Request,
    db: DbSession,
    intake_key: Annotated[str | None, Header(alias="X-Nexyra-Intake-Key")] = None,
    idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
) -> ExternalLeadIntakeRead:
    service = IntegrationService(db)
    try:
        source, workspace = service.authenticate_external_source(
            integration_public_id,
            intake_key,
        )
        if idempotency_key is not None:
            idempotency_key = idempotency_key.strip() or None
            if idempotency_key and len(idempotency_key) > 160:
                raise HTTPException(
                    status_code=422,
                    detail="X-Idempotency-Key deve ter no máximo 160 caracteres.",
                )

        normalized_payload = build_external_lead_payload(
            source,
            payload,
            idempotency_key=idempotency_key,
        )
        db.info["audit_actor_type"] = "integration"
        db.info.pop("audit_actor_membership_id", None)
        action, view = LeadService(db).intake(
            workspace.public_id,
            normalized_payload,
        )
        updated_source = service.record_external_intake(
            source,
            lead_public_id=view.lead.public_id,
            action=action,
            request_id=getattr(request.state, "request_id", None),
            idempotency_key=idempotency_key,
            remote_ip=request.client.host if request.client else None,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_input=False),
        ) from exc
    except ValueError as exc:
        _translate_error(exc)
        raise

    return ExternalLeadIntakeRead(
        action=action,
        lead_public_id=view.lead.public_id,
        source=view.lead.source,
        channel=view.lead.channel,
        campaign=view.lead.campaign,
        intake_count=updated_source.intake_count,
    )


@router.post(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/activate",
    response_model=IntegrationSourceRead,
)
def activate_integration(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> IntegrationSourceRead:
    try:
        item = IntegrationService(db).set_active(
            workspace_public_id,
            integration_public_id,
            active=True,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return IntegrationSourceRead.model_validate(item)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/deactivate",
    response_model=IntegrationSourceRead,
)
def deactivate_integration(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> IntegrationSourceRead:
    try:
        item = IntegrationService(db).set_active(
            workspace_public_id,
            integration_public_id,
            active=False,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return IntegrationSourceRead.model_validate(item)
