from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.integrations.atlas.contract import ATLAS_CONTRACT_NAME
from app.integrations.atlas.schemas import (
    AtlasActionExecuteRequest,
    AtlasActionExecutionRead,
    AtlasActionPreviewRead,
    AtlasActionRequest,
    AtlasCapabilitiesRead,
    AtlasHealthRead,
    AtlasWorkspaceContextRead,
)
from app.integrations.atlas.security import (
    AtlasIntegrationForbiddenError,
    AtlasIntegrationSecurity,
    AtlasIntegrationUnauthorizedError,
    AtlasIntegrationWorkspaceError,
)
from app.integrations.atlas.service import (
    AtlasActionValidationError,
    AtlasConfirmationRequiredError,
    AtlasIntegrationService,
)
from app.schemas import LeadCreate

router = APIRouter(
    prefix="/integrations/atlas",
    tags=["atlas-integration"],
)

DbSession = Annotated[Session, Depends(get_db)]
IntegrationToken = Annotated[
    str,
    Header(alias="X-Nexyra-Integration-Token"),
]
ActorUser = Annotated[
    str,
    Header(alias="X-Nexyra-Actor-User"),
]


def _translate_security_error(exc: ValueError) -> None:
    if isinstance(exc, AtlasIntegrationUnauthorizedError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, AtlasIntegrationForbiddenError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, AtlasIntegrationWorkspaceError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise exc


def _authorize(
    *,
    db: Session,
    workspace_public_id: str,
    token: str,
    actor_user_public_id: str,
    permission: str,
):
    security = AtlasIntegrationSecurity(db)
    try:
        security.verify_token(token)
        return security.authorize(
            workspace_public_id=workspace_public_id,
            actor_user_public_id=actor_user_public_id,
            required_permission=permission,
        )
    except ValueError as exc:
        _translate_security_error(exc)
        raise


@router.get(
    "/health",
    response_model=AtlasHealthRead,
)
def atlas_integration_health() -> AtlasHealthRead:
    settings = get_settings()
    return AtlasHealthRead(
        ok=True,
        product=settings.app_name,
        crm_version=settings.app_version,
        contract_name=ATLAS_CONTRACT_NAME,
        contract_version=settings.atlas_contract_version,
    )


@router.get(
    "/capabilities",
    response_model=AtlasCapabilitiesRead,
)
def atlas_capabilities(
    token: IntegrationToken,
    db: DbSession,
) -> AtlasCapabilitiesRead:
    security = AtlasIntegrationSecurity(db)
    try:
        security.verify_token(token)
    except ValueError as exc:
        _translate_security_error(exc)
        raise

    settings = get_settings()
    payload = AtlasIntegrationService.capabilities(
        contract_version=settings.atlas_contract_version
    )
    return AtlasCapabilitiesRead(**payload)


@router.get(
    "/workspaces/{workspace_public_id}/context",
    response_model=AtlasWorkspaceContextRead,
)
def atlas_workspace_context(
    workspace_public_id: str,
    token: IntegrationToken,
    actor_user_public_id: ActorUser,
    db: DbSession,
) -> AtlasWorkspaceContextRead:
    workspace, user, membership, permissions = _authorize(
        db=db,
        workspace_public_id=workspace_public_id,
        token=token,
        actor_user_public_id=actor_user_public_id,
        permission="atlas.use",
    )

    settings = get_settings()
    payload = AtlasIntegrationService(db).workspace_context(
        workspace=workspace,
        actor_user=user,
        membership=membership,
        permissions=permissions,
        contract_version=settings.atlas_contract_version,
    )
    return AtlasWorkspaceContextRead(**payload)


@router.post(
    "/workspaces/{workspace_public_id}/lead-intake",
)
def atlas_lead_intake(
    workspace_public_id: str,
    payload: LeadCreate,
    token: IntegrationToken,
    actor_user_public_id: ActorUser,
    db: DbSession,
) -> dict[str, object]:
    workspace, _, membership, _ = _authorize(
        db=db,
        workspace_public_id=workspace_public_id,
        token=token,
        actor_user_public_id=actor_user_public_id,
        permission="atlas.execute",
    )

    try:
        action, lead = AtlasIntegrationService(db).intake_lead(
            workspace=workspace,
            actor_membership=membership,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "contract_version": get_settings().atlas_contract_version,
        "action": action,
        "lead": lead,
    }


@router.post(
    "/workspaces/{workspace_public_id}/actions/preview",
    response_model=AtlasActionPreviewRead,
)
def atlas_action_preview(
    workspace_public_id: str,
    payload: AtlasActionRequest,
    token: IntegrationToken,
    actor_user_public_id: ActorUser,
    db: DbSession,
) -> AtlasActionPreviewRead:
    workspace, _, _, _ = _authorize(
        db=db,
        workspace_public_id=workspace_public_id,
        token=token,
        actor_user_public_id=actor_user_public_id,
        permission="atlas.use",
    )

    try:
        result = AtlasIntegrationService(db).preview_action(
            workspace=workspace,
            request=payload,
            contract_version=get_settings().atlas_contract_version,
        )
    except (AtlasActionValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return AtlasActionPreviewRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/actions/execute",
    response_model=AtlasActionExecutionRead,
)
def atlas_action_execute(
    workspace_public_id: str,
    payload: AtlasActionExecuteRequest,
    token: IntegrationToken,
    actor_user_public_id: ActorUser,
    db: DbSession,
) -> AtlasActionExecutionRead:
    workspace, user, membership, _ = _authorize(
        db=db,
        workspace_public_id=workspace_public_id,
        token=token,
        actor_user_public_id=actor_user_public_id,
        permission="atlas.execute",
    )

    try:
        result = AtlasIntegrationService(db).execute_action(
            workspace=workspace,
            actor_user=user,
            actor_membership=membership,
            request=payload,
            contract_version=get_settings().atlas_contract_version,
        )
    except AtlasConfirmationRequiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (AtlasActionValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return AtlasActionExecutionRead(**result)
