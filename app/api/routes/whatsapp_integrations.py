from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.integrations.whatsapp_cloud import WhatsAppGraphError
from app.schemas.whatsapp_integration import (
    WhatsAppCoexistenceSyncRead,
    WhatsAppCoexistenceSyncRequest,
    WhatsAppConfigure,
    WhatsAppConnectionTestRead,
    WhatsAppEmbeddedSignupComplete,
    WhatsAppEmbeddedSignupCompleteRead,
    WhatsAppEmbeddedSignupConfigRead,
    WhatsAppEmbeddedSignupSelectPhone,
    WhatsAppMessagePreview,
    WhatsAppMessagePreviewRead,
    WhatsAppMessageRead,
    WhatsAppMessageSend,
    WhatsAppMessageSendRead,
    WhatsAppStatusRead,
    WhatsAppSubscriptionRead,
    WhatsAppTemplatePreviewRead,
    WhatsAppTemplatePreviewRequest,
    WhatsAppTemplateRead,
    WhatsAppTemplateSend,
    WhatsAppWebhookRead,
)
from app.security.whatsapp_confirmation import WhatsAppConfirmationError
from app.services.communication_consent import CommunicationBlockedError
from app.services.integration import (
    IntegrationSourceNotFoundError,
    IntegrationWorkspaceNotFoundError,
)
from app.services.whatsapp_cloud import (
    WhatsAppCloudService,
    WhatsAppIntegrationConflictError,
    WhatsAppIntegrationError,
    WhatsAppNotConfiguredError,
    WhatsAppSignatureError,
)

router = APIRouter(tags=["whatsapp"])
DbSession = Annotated[Session, Depends(get_db)]
CanReadSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.read")),
]
CanUpdateSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.update")),
]
CanSendWhatsApp = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("activities.create")),
]


def _translate_error(exc: ValueError) -> None:
    if isinstance(
        exc,
        (IntegrationWorkspaceNotFoundError, IntegrationSourceNotFoundError),
    ):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, WhatsAppSignatureError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WhatsAppNotConfiguredError,
            WhatsAppIntegrationConflictError,
            WhatsAppConfirmationError,
            CommunicationBlockedError,
        ),
    ):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, WhatsAppGraphError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, WhatsAppIntegrationError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp",
    response_model=WhatsAppStatusRead,
)
def whatsapp_status(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
) -> WhatsAppStatusRead:
    try:
        payload = WhatsAppCloudService(db).status(
            workspace_public_id,
            integration_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppStatusRead(**payload)


@router.put(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp",
    response_model=WhatsAppStatusRead,
)
def configure_whatsapp(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppConfigure,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WhatsAppStatusRead:
    try:
        result = WhatsAppCloudService(db).configure(
            workspace_public_id,
            integration_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppStatusRead(**result)


@router.delete(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp",
    response_model=WhatsAppStatusRead,
)
def disconnect_whatsapp(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WhatsAppStatusRead:
    try:
        result = WhatsAppCloudService(db).disconnect(
            workspace_public_id,
            integration_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppStatusRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/test",
    response_model=WhatsAppConnectionTestRead,
)
def test_whatsapp_connection(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WhatsAppConnectionTestRead:
    try:
        result = WhatsAppCloudService(db).test_connection(
            workspace_public_id,
            integration_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppConnectionTestRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/subscribe",
    response_model=WhatsAppSubscriptionRead,
)
def subscribe_whatsapp_webhook(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WhatsAppSubscriptionRead:
    try:
        result = WhatsAppCloudService(db).subscribe_business_account(
            workspace_public_id,
            integration_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppSubscriptionRead(**result)


@router.get(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/embedded-signup/config",
    response_model=WhatsAppEmbeddedSignupConfigRead,
)
def embedded_signup_config(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
) -> WhatsAppEmbeddedSignupConfigRead:
    try:
        service = WhatsAppCloudService(db)
        service._source(workspace_public_id, integration_public_id)
        result = service.embedded_signup_config()
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppEmbeddedSignupConfigRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/embedded-signup/complete",
    response_model=WhatsAppEmbeddedSignupCompleteRead,
)
def complete_embedded_signup(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppEmbeddedSignupComplete,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WhatsAppEmbeddedSignupCompleteRead:
    try:
        result = WhatsAppCloudService(db).complete_embedded_signup(
            workspace_public_id,
            integration_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppEmbeddedSignupCompleteRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/embedded-signup/select-phone",
    response_model=WhatsAppEmbeddedSignupCompleteRead,
)
def select_embedded_signup_phone(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppEmbeddedSignupSelectPhone,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WhatsAppEmbeddedSignupCompleteRead:
    try:
        result = WhatsAppCloudService(db).select_embedded_signup_phone(
            workspace_public_id,
            integration_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppEmbeddedSignupCompleteRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/coexistence/sync",
    response_model=WhatsAppCoexistenceSyncRead,
)
def request_coexistence_sync(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppCoexistenceSyncRequest,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WhatsAppCoexistenceSyncRead:
    try:
        result = WhatsAppCloudService(db).request_coexistence_sync(
            workspace_public_id,
            integration_public_id,
            sync_type=payload.sync_type,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppCoexistenceSyncRead(**result)


@router.get(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/templates",
    response_model=list[WhatsAppTemplateRead],
)
def whatsapp_templates(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[WhatsAppTemplateRead]:
    try:
        items = WhatsAppCloudService(db).list_templates(
            workspace_public_id,
            integration_public_id,
            limit=limit,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [WhatsAppTemplateRead(**item) for item in items]


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/templates/preview",
    response_model=WhatsAppTemplatePreviewRead,
)
def preview_whatsapp_template(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppTemplatePreviewRequest,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> WhatsAppTemplatePreviewRead:
    try:
        result = WhatsAppCloudService(db).preview_template(
            workspace_public_id,
            integration_public_id,
            to=payload.to,
            template_name=payload.template_name,
            language_code=payload.language_code,
            parameters=payload.parameters,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppTemplatePreviewRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/templates/send",
    response_model=WhatsAppMessageSendRead,
)
def send_whatsapp_template(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppTemplateSend,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> WhatsAppMessageSendRead:
    try:
        result = WhatsAppCloudService(db).send_template(
            workspace_public_id,
            integration_public_id,
            to=payload.to,
            template_name=payload.template_name,
            language_code=payload.language_code,
            parameters=payload.parameters,
            confirmation_token=payload.confirmation_token,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppMessageSendRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/messages/preview",
    response_model=WhatsAppMessagePreviewRead,
)
def preview_whatsapp_message(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppMessagePreview,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> WhatsAppMessagePreviewRead:
    try:
        result = WhatsAppCloudService(db).preview_message(
            workspace_public_id,
            integration_public_id,
            to=payload.to,
            text=payload.text,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppMessagePreviewRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/messages/send",
    response_model=WhatsAppMessageSendRead,
)
def send_whatsapp_message(
    workspace_public_id: str,
    integration_public_id: str,
    payload: WhatsAppMessageSend,
    db: DbSession,
    _authorization: CanSendWhatsApp,
) -> WhatsAppMessageSendRead:
    try:
        result = WhatsAppCloudService(db).send_message(
            workspace_public_id,
            integration_public_id,
            to=payload.to,
            text=payload.text,
            confirmation_token=payload.confirmation_token,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppMessageSendRead(**result)


@router.get(
    "/workspaces/{workspace_public_id}/integrations/"
    "{integration_public_id}/whatsapp/messages",
    response_model=list[WhatsAppMessageRead],
)
def recent_whatsapp_messages(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[WhatsAppMessageRead]:
    try:
        items = WhatsAppCloudService(db).recent_messages(
            workspace_public_id,
            integration_public_id,
            limit=limit,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [
        WhatsAppMessageRead(
            public_id=item.public_id,
            provider_message_id=item.provider_message_id,
            direction=item.direction,
            message_type=item.message_type,
            from_phone=item.from_phone,
            to_phone=item.to_phone,
            body=item.body,
            status=item.status,
            error_code=item.error_code,
            error_message=item.error_message,
            provider_timestamp=item.provider_timestamp,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
def verify_whatsapp_webhook(
    db: DbSession,
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> str:
    try:
        return WhatsAppCloudService(db).verify_challenge(
            mode,
            token,
            challenge,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise


@router.post("/whatsapp/webhook", response_model=WhatsAppWebhookRead)
async def receive_whatsapp_webhook(
    request: Request,
    db: DbSession,
    signature: Annotated[
        str | None,
        Header(alias="X-Hub-Signature-256"),
    ] = None,
) -> WhatsAppWebhookRead:
    raw_body = await request.body()
    try:
        result = WhatsAppCloudService(db).handle_webhook(
            raw_body=raw_body,
            signature=signature,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return WhatsAppWebhookRead(
        messages=result.messages,
        statuses=result.statuses,
        created=result.created,
        updated=result.updated,
        ignored=result.ignored,
        echoes=result.echoes,
        history_events=result.history_events,
        contact_sync_events=result.contact_sync_events,
    )
