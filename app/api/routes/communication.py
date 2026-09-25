from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas.communication import (
    COMMUNICATION_CHANNELS,
    CommunicationEligibilityRead,
    CommunicationPolicyRead,
    CommunicationPolicyUpdate,
    LeadCommunicationSummaryRead,
    LeadConsentRead,
    LeadConsentUpsert,
    LeadOptOutRequest,
)
from app.services.communication_consent import (
    CommunicationConsentError,
    CommunicationConsentService,
    CommunicationLeadNotFoundError,
)
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["communication"])
DbSession = Annotated[Session, Depends(get_db)]
CanRead = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.read")),
]
CanUpdateLead = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.update")),
]
CanManagePolicy = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.update")),
]
ChannelQuery = Annotated[str, Query(max_length=30)]


def _error(exc: ValueError) -> None:
    if isinstance(exc, (WorkspaceNotFoundError, CommunicationLeadNotFoundError)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, CommunicationConsentError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


def _policy_read(policy) -> CommunicationPolicyRead:
    return CommunicationPolicyRead(
        enforce_whatsapp_opt_in=policy.enforce_whatsapp_opt_in,
        enforce_email_opt_in=policy.enforce_email_opt_in,
        enforce_sms_opt_in=policy.enforce_sms_opt_in,
        enforce_phone_opt_in=policy.enforce_phone_opt_in,
        allow_legacy_lead_consent=policy.allow_legacy_lead_consent,
        stop_cadence_on_block=policy.stop_cadence_on_block,
        updated_at=policy.updated_at,
    )


def _consent_read(view) -> LeadConsentRead:
    item = view.item
    return LeadConsentRead(
        public_id=item.public_id if item is not None else None,
        channel=view.channel,
        status=item.status if item is not None else "unknown",
        lawful_basis=item.lawful_basis if item is not None else None,
        source=item.source if item is not None else None,
        evidence=item.evidence if item is not None else None,
        note=item.note if item is not None else None,
        granted_at=item.granted_at if item is not None else None,
        revoked_at=item.revoked_at if item is not None else None,
        updated_at=item.updated_at if item is not None else None,
        explicit=item is not None,
        allowed=view.eligibility.allowed,
        effective_reason=view.eligibility.reason,
    )


@router.get(
    "/workspaces/{workspace_public_id}/communication-policy",
    response_model=CommunicationPolicyRead,
)
def get_policy(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanRead,
) -> CommunicationPolicyRead:
    try:
        policy = CommunicationConsentService(db).get_policy(
            workspace_public_id
        )
    except ValueError as exc:
        _error(exc)
        raise
    return _policy_read(policy)


@router.put(
    "/workspaces/{workspace_public_id}/communication-policy",
    response_model=CommunicationPolicyRead,
)
def update_policy(
    workspace_public_id: str,
    payload: CommunicationPolicyUpdate,
    db: DbSession,
    _authorization: CanManagePolicy,
) -> CommunicationPolicyRead:
    try:
        policy = CommunicationConsentService(db).update_policy(
            workspace_public_id,
            payload,
        )
    except ValueError as exc:
        _error(exc)
        raise
    return _policy_read(policy)


@router.get(
    "/workspaces/{workspace_public_id}/leads/{lead_public_id}/communication-consents",
    response_model=LeadCommunicationSummaryRead,
)
def list_consents(
    workspace_public_id: str,
    lead_public_id: str,
    db: DbSession,
    _authorization: CanRead,
) -> LeadCommunicationSummaryRead:
    service = CommunicationConsentService(db)
    try:
        lead, views = service.list_for_lead(
            workspace_public_id,
            lead_public_id,
        )
    except ValueError as exc:
        _error(exc)
        raise
    return LeadCommunicationSummaryRead(
        lead_public_id=lead.public_id,
        legacy_consent=lead.consent,
        global_opt_out=service.has_global_opt_out(lead),
        items=[_consent_read(view) for view in views],
    )


@router.put(
    "/workspaces/{workspace_public_id}/leads/{lead_public_id}/communication-consents",
    response_model=LeadCommunicationSummaryRead,
)
def upsert_consent(
    workspace_public_id: str,
    lead_public_id: str,
    payload: LeadConsentUpsert,
    db: DbSession,
    _authorization: CanUpdateLead,
) -> LeadCommunicationSummaryRead:
    service = CommunicationConsentService(db)
    try:
        service.upsert(workspace_public_id, lead_public_id, payload)
        lead, views = service.list_for_lead(
            workspace_public_id,
            lead_public_id,
        )
    except ValueError as exc:
        _error(exc)
        raise
    return LeadCommunicationSummaryRead(
        lead_public_id=lead.public_id,
        legacy_consent=lead.consent,
        global_opt_out=service.has_global_opt_out(lead),
        items=[_consent_read(view) for view in views],
    )


@router.post(
    "/workspaces/{workspace_public_id}/leads/{lead_public_id}/communication-opt-out",
    response_model=LeadCommunicationSummaryRead,
)
def opt_out(
    workspace_public_id: str,
    lead_public_id: str,
    payload: LeadOptOutRequest,
    db: DbSession,
    _authorization: CanUpdateLead,
) -> LeadCommunicationSummaryRead:
    service = CommunicationConsentService(db)
    try:
        service.opt_out(
            workspace_public_id,
            lead_public_id,
            channel=payload.channel,
            source=payload.source,
            reason=payload.reason,
        )
        lead, views = service.list_for_lead(
            workspace_public_id,
            lead_public_id,
        )
    except ValueError as exc:
        _error(exc)
        raise
    return LeadCommunicationSummaryRead(
        lead_public_id=lead.public_id,
        legacy_consent=lead.consent,
        global_opt_out=service.has_global_opt_out(lead),
        items=[_consent_read(view) for view in views],
    )


@router.get(
    "/workspaces/{workspace_public_id}/leads/{lead_public_id}/communication-eligibility",
    response_model=CommunicationEligibilityRead,
)
def eligibility(
    workspace_public_id: str,
    lead_public_id: str,
    db: DbSession,
    _authorization: CanRead,
    channel: ChannelQuery = "whatsapp",
) -> CommunicationEligibilityRead:
    normalized = channel.strip().lower()
    if normalized not in COMMUNICATION_CHANNELS:
        raise HTTPException(
            status_code=422,
            detail="Canal de comunicação inválido.",
        )
    try:
        result = CommunicationConsentService(db).eligibility(
            workspace_public_id,
            lead_public_id,
            normalized,
        )
    except ValueError as exc:
        _error(exc)
        raise
    return CommunicationEligibilityRead(
        lead_public_id=lead_public_id,
        channel=normalized,
        allowed=result.allowed,
        reason=result.reason,
    )
