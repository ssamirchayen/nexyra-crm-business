from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.integrations.whatsapp_cloud import WhatsAppGraphError
from app.schemas.whatsapp_bulk import (
    WhatsAppBulkPreviewRead,
    WhatsAppBulkPreviewRequest,
    WhatsAppBulkSendRead,
    WhatsAppBulkSendRequest,
    WhatsAppBulkSourceRead,
)
from app.schemas.whatsapp_integration import WhatsAppTemplateRead
from app.security.whatsapp_confirmation import WhatsAppConfirmationError
from app.services.communication_consent import CommunicationBlockedError
from app.services.integration import IntegrationSourceNotFoundError
from app.services.lead import LeadNotFoundError
from app.services.whatsapp_bulk import WhatsAppBulkError, WhatsAppBulkService
from app.services.whatsapp_cloud import (
    WhatsAppCloudService,
    WhatsAppIntegrationError,
    WhatsAppNotConfiguredError,
)
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["whatsapp-bulk"])
DbSession = Annotated[Session, Depends(get_db)]
CanSendWhatsApp = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("activities.create")),
]


def _translate_error(exc: ValueError) -> None:
    if isinstance(
        exc,
        (WorkspaceNotFoundError, LeadNotFoundError, IntegrationSourceNotFoundError),
    ):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WhatsAppBulkError,
            WhatsAppConfirmationError,
            WhatsAppNotConfiguredError,
            WhatsAppIntegrationError,
            CommunicationBlockedError,
        ),
    ):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, WhatsAppGraphError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


@router.get(
    "/workspaces/{workspace_public_id}/whatsapp/bulk/sources",
    response_model=list[WhatsAppBulkSourceRead],
)
def bulk_whatsapp_sources(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> list[WhatsAppBulkSourceRead]:
    try:
        items = WhatsAppBulkService(db).source_options(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [WhatsAppBulkSourceRead(**item) for item in items]


@router.get(
    "/workspaces/{workspace_public_id}/whatsapp/bulk/templates/{integration_public_id}",
    response_model=list[WhatsAppTemplateRead],
)
def bulk_whatsapp_templates(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> list[WhatsAppTemplateRead]:
    try:
        items = WhatsAppCloudService(db).list_templates(
            workspace_public_id,
            integration_public_id,
            limit=100,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [WhatsAppTemplateRead(**item) for item in items]


@router.post(
    "/workspaces/{workspace_public_id}/whatsapp/bulk/preview",
    response_model=WhatsAppBulkPreviewRead,
)
def preview_bulk_whatsapp(
    workspace_public_id: str,
    payload: WhatsAppBulkPreviewRequest,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> WhatsAppBulkPreviewRead:
    try:
        result = WhatsAppBulkService(db).preview(workspace_public_id, payload)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppBulkPreviewRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/whatsapp/bulk/send",
    response_model=WhatsAppBulkSendRead,
)
def send_bulk_whatsapp(
    workspace_public_id: str,
    payload: WhatsAppBulkSendRequest,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> WhatsAppBulkSendRead:
    try:
        result = WhatsAppBulkService(db).send(workspace_public_id, payload)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppBulkSendRead(**result)
