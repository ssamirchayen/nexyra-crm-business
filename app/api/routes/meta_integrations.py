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
from app.integrations.meta_lead_ads import MetaGraphError
from app.schemas.meta_integration import (
    MetaLeadAdsConfigure,
    MetaLeadAdsConnectionTestRead,
    MetaLeadAdsStatusRead,
    MetaLeadAdsSubscriptionRead,
    MetaWebhookRead,
)
from app.services.meta_lead_ads import (
    MetaIntegrationConflictError,
    MetaIntegrationError,
    MetaIntegrationNotConfiguredError,
    MetaLeadAdsService,
    MetaSignatureError,
)

router = APIRouter(tags=["meta-integrations"])
DbSession = Annotated[Session, Depends(get_db)]
CanReadSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.read")),
]
CanUpdateSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.update")),
]


def _translate(exc: ValueError) -> None:
    if isinstance(exc, MetaSignatureError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, MetaIntegrationNotConfiguredError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, MetaIntegrationConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, (MetaIntegrationError, MetaGraphError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/meta",
    response_model=MetaLeadAdsStatusRead,
)
def meta_status(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanReadSettings,
) -> MetaLeadAdsStatusRead:
    try:
        data = MetaLeadAdsService(db).status(workspace_public_id, integration_public_id)
    except ValueError as exc:
        _translate(exc)
        raise
    return MetaLeadAdsStatusRead(**data)


@router.put(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/meta",
    response_model=MetaLeadAdsStatusRead,
)
def configure_meta(
    workspace_public_id: str,
    integration_public_id: str,
    payload: MetaLeadAdsConfigure,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> MetaLeadAdsStatusRead:
    try:
        data = MetaLeadAdsService(db).configure(
            workspace_public_id, integration_public_id, payload
        )
    except ValueError as exc:
        _translate(exc)
        raise
    return MetaLeadAdsStatusRead(**data)


@router.delete(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/meta",
    response_model=MetaLeadAdsStatusRead,
)
def disconnect_meta(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> MetaLeadAdsStatusRead:
    try:
        data = MetaLeadAdsService(db).disconnect(
            workspace_public_id, integration_public_id
        )
    except ValueError as exc:
        _translate(exc)
        raise
    return MetaLeadAdsStatusRead(**data)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/meta/subscribe",
    response_model=MetaLeadAdsSubscriptionRead,
)
def subscribe_meta_page(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> MetaLeadAdsSubscriptionRead:
    try:
        data = MetaLeadAdsService(db).subscribe_page(
            workspace_public_id, integration_public_id
        )
    except ValueError as exc:
        _translate(exc)
        raise
    return MetaLeadAdsSubscriptionRead(**data)


@router.post(
    "/workspaces/{workspace_public_id}/integrations/{integration_public_id}/meta/test",
    response_model=MetaLeadAdsConnectionTestRead,
)
def test_meta_connection(
    workspace_public_id: str,
    integration_public_id: str,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> MetaLeadAdsConnectionTestRead:
    try:
        data = MetaLeadAdsService(db).test_connection(
            workspace_public_id, integration_public_id
        )
    except ValueError as exc:
        _translate(exc)
        raise
    return MetaLeadAdsConnectionTestRead(**data)


@router.get("/meta/webhook", response_class=PlainTextResponse)
def verify_meta_webhook(
    db: DbSession,
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    try:
        challenge = MetaLeadAdsService(db).verify_challenge(
            hub_mode, hub_verify_token, hub_challenge
        )
    except ValueError as exc:
        _translate(exc)
        raise
    return PlainTextResponse(challenge)


@router.post("/meta/webhook", response_model=MetaWebhookRead)
async def receive_meta_webhook(
    request: Request,
    db: DbSession,
    signature: Annotated[
        str | None,
        Header(alias="X-Hub-Signature-256"),
    ] = None,
) -> MetaWebhookRead:
    raw_body = await request.body()
    try:
        result = MetaLeadAdsService(db).process_webhook(
            raw_body,
            signature=signature,
            request_id=getattr(request.state, "request_id", None),
            remote_ip=request.client.host if request.client else None,
        )
    except ValueError as exc:
        _translate(exc)
        raise
    return MetaWebhookRead(
        events=result.events,
        created=result.created,
        updated=result.updated,
        ignored=result.ignored,
    )
