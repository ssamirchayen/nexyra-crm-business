from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Lead,
    LeadCommunicationConsent,
    WorkspaceCommunicationPolicy,
)
from app.repositories import LeadRepository, WorkspaceRepository
from app.schemas.communication import (
    COMMUNICATION_CHANNELS,
    CommunicationPolicyUpdate,
    LeadConsentUpsert,
)
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError


class CommunicationConsentError(ValueError):
    pass


class CommunicationLeadNotFoundError(CommunicationConsentError):
    pass


class CommunicationBlockedError(CommunicationConsentError):
    pass


@dataclass(frozen=True, slots=True)
class Eligibility:
    allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ConsentView:
    item: LeadCommunicationConsent | None
    channel: str
    eligibility: Eligibility


class CommunicationConsentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.leads = LeadRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {public_id}"
            )
        return workspace

    def _lead(self, workspace_id: int, lead_public_id: str) -> Lead:
        lead = self.leads.get_by_public_id(
            workspace_id=workspace_id,
            public_id=lead_public_id,
        )
        if lead is None:
            raise CommunicationLeadNotFoundError(
                f"Lead não encontrado: {lead_public_id}"
            )
        return lead

    def _policy_by_workspace_id(
        self,
        workspace_id: int,
        *,
        create: bool = True,
    ) -> WorkspaceCommunicationPolicy:
        policy = self.db.scalar(
            select(WorkspaceCommunicationPolicy).where(
                WorkspaceCommunicationPolicy.workspace_id == workspace_id
            )
        )
        if policy is not None:
            return policy
        policy = WorkspaceCommunicationPolicy(workspace_id=workspace_id)
        if create:
            self.db.add(policy)
            self.db.flush()
        return policy

    def get_policy(
        self,
        workspace_public_id: str,
    ) -> WorkspaceCommunicationPolicy:
        workspace = self._workspace(workspace_public_id)
        policy = self._policy_by_workspace_id(workspace.id)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def update_policy(
        self,
        workspace_public_id: str,
        payload: CommunicationPolicyUpdate,
    ) -> WorkspaceCommunicationPolicy:
        workspace = self._workspace(workspace_public_id)
        policy = self._policy_by_workspace_id(workspace.id)
        before = self._policy_snapshot(policy)
        for key, value in payload.model_dump().items():
            setattr(policy, key, value)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="communication_policy",
            entity_public_id=workspace.public_id,
            action="communication_policy.updated",
            before_data=before,
            after_data=self._policy_snapshot(policy),
        )
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def _consent(
        self,
        *,
        lead_id: int,
        channel: str,
    ) -> LeadCommunicationConsent | None:
        return self.db.scalar(
            select(LeadCommunicationConsent).where(
                LeadCommunicationConsent.lead_id == lead_id,
                LeadCommunicationConsent.channel == channel,
            )
        )

    def list_for_lead(
        self,
        workspace_public_id: str,
        lead_public_id: str,
    ) -> tuple[Lead, list[ConsentView]]:
        workspace = self._workspace(workspace_public_id)
        lead = self._lead(workspace.id, lead_public_id)
        policy = self._policy_by_workspace_id(workspace.id)
        rows = list(
            self.db.scalars(
                select(LeadCommunicationConsent).where(
                    LeadCommunicationConsent.lead_id == lead.id
                )
            ).all()
        )
        by_channel = {row.channel: row for row in rows}
        global_item = by_channel.get("all")
        views = [
            ConsentView(
                item=by_channel.get(channel),
                channel=channel,
                eligibility=self._evaluate(
                    lead=lead,
                    channel=channel,
                    policy=policy,
                    channel_item=by_channel.get(channel),
                    global_item=global_item,
                ),
            )
            for channel in sorted(COMMUNICATION_CHANNELS)
        ]
        return lead, views

    def upsert(
        self,
        workspace_public_id: str,
        lead_public_id: str,
        payload: LeadConsentUpsert,
    ) -> LeadCommunicationConsent:
        workspace = self._workspace(workspace_public_id)
        lead = self._lead(workspace.id, lead_public_id)
        item = self._consent(lead_id=lead.id, channel=payload.channel)
        before = self._consent_snapshot(item) if item is not None else None
        if item is None:
            item = LeadCommunicationConsent(
                workspace_id=workspace.id,
                lead_id=lead.id,
                channel=payload.channel,
            )
            self.db.add(item)
        now = datetime.now(timezone.utc)
        item.status = payload.status
        item.lawful_basis = payload.lawful_basis
        item.source = payload.source
        item.evidence = payload.evidence
        item.note = payload.note
        if payload.status == "granted":
            item.granted_at = now
            item.revoked_at = None
            if item.lawful_basis is None:
                item.lawful_basis = "consent"
        elif payload.status in {"revoked", "denied"}:
            item.revoked_at = now
        else:
            item.granted_at = None
            item.revoked_at = None
        if payload.channel == "all" and payload.status in {"revoked", "denied"}:
            lead.consent = False
            self.leads.save(lead)
        self.db.flush()
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead_communication_consent",
            entity_public_id=item.public_id,
            action="communication_consent.updated",
            before_data=before,
            after_data=self._consent_snapshot(item),
            metadata={"lead_public_id": lead.public_id},
        )
        self.db.commit()
        self.db.refresh(item)
        return item

    def opt_out(
        self,
        workspace_public_id: str,
        lead_public_id: str,
        *,
        channel: str,
        source: str | None,
        reason: str | None,
    ) -> LeadCommunicationConsent:
        return self.upsert(
            workspace_public_id,
            lead_public_id,
            LeadConsentUpsert(
                channel=channel,
                status="revoked",
                source=source or "manual",
                note=reason,
            ),
        )

    def eligibility(
        self,
        workspace_public_id: str,
        lead_public_id: str,
        channel: str,
    ) -> Eligibility:
        workspace = self._workspace(workspace_public_id)
        lead = self._lead(workspace.id, lead_public_id)
        return self.eligibility_for_lead(lead, channel)

    def eligibility_for_lead(
        self,
        lead: Lead,
        channel: str,
    ) -> Eligibility:
        normalized = channel.strip().lower()
        if normalized not in COMMUNICATION_CHANNELS:
            raise CommunicationConsentError(
                f"Canal de comunicação não suportado: {channel}"
            )
        policy = self._policy_by_workspace_id(lead.workspace_id)
        return self._evaluate(
            lead=lead,
            channel=normalized,
            policy=policy,
            channel_item=self._consent(
                lead_id=lead.id,
                channel=normalized,
            ),
            global_item=self._consent(lead_id=lead.id, channel="all"),
        )

    def assert_allowed_for_lead(
        self,
        lead: Lead,
        channel: str,
    ) -> None:
        result = self.eligibility_for_lead(lead, channel)
        if not result.allowed:
            raise CommunicationBlockedError(
                f"Comunicação por {channel} bloqueada: {result.reason}."
            )

    def assert_phone_allowed(
        self,
        *,
        workspace_id: int,
        phone: str,
        channel: str = "whatsapp",
    ) -> Lead | None:
        normalized_phone = "".join(char for char in phone if char.isdigit())
        lead = self.leads.find_duplicate(
            workspace_id=workspace_id,
            normalized_phone=normalized_phone or None,
            normalized_email=None,
            external_id=None,
        )
        if lead is None:
            # Compatibilidade: números ainda não vinculados a um lead continuam
            # disponíveis para o fluxo manual. As regras de opt-out são aplicadas
            # assim que existe um lead identificável no CRM.
            return None
        self.assert_allowed_for_lead(lead, channel)
        return lead

    def has_global_opt_out(self, lead: Lead) -> bool:
        item = self._consent(lead_id=lead.id, channel="all")
        return bool(
            item is not None and item.status in {"revoked", "denied"}
        )

    def should_stop_cadence(self, workspace_id: int) -> bool:
        return self._policy_by_workspace_id(
            workspace_id
        ).stop_cadence_on_block

    def _evaluate(
        self,
        *,
        lead: Lead,
        channel: str,
        policy: WorkspaceCommunicationPolicy,
        channel_item: LeadCommunicationConsent | None,
        global_item: LeadCommunicationConsent | None,
    ) -> Eligibility:
        if global_item is not None and global_item.status in {
            "revoked",
            "denied",
        }:
            return Eligibility(False, "opt-out global registrado")
        if channel_item is not None:
            if channel_item.status == "granted":
                return Eligibility(True, "autorização explícita do canal")
            if channel_item.status in {"revoked", "denied"}:
                return Eligibility(False, "opt-out explícito do canal")
        if global_item is not None and global_item.status == "granted":
            return Eligibility(True, "autorização global explícita")
        if policy.allow_legacy_lead_consent and lead.consent:
            return Eligibility(True, "consentimento legado do lead")
        if not self._channel_enforced(policy, channel):
            return Eligibility(True, "canal não exige opt-in pela política")
        return Eligibility(False, "opt-in não registrado")

    @staticmethod
    def _channel_enforced(
        policy: WorkspaceCommunicationPolicy,
        channel: str,
    ) -> bool:
        mapping = {
            "whatsapp": policy.enforce_whatsapp_opt_in,
            "email": policy.enforce_email_opt_in,
            "sms": policy.enforce_sms_opt_in,
            "phone": policy.enforce_phone_opt_in,
        }
        return bool(mapping.get(channel, True))

    @staticmethod
    def _policy_snapshot(
        policy: WorkspaceCommunicationPolicy,
    ) -> dict[str, object]:
        return {
            "enforce_whatsapp_opt_in": policy.enforce_whatsapp_opt_in,
            "enforce_email_opt_in": policy.enforce_email_opt_in,
            "enforce_sms_opt_in": policy.enforce_sms_opt_in,
            "enforce_phone_opt_in": policy.enforce_phone_opt_in,
            "allow_legacy_lead_consent": policy.allow_legacy_lead_consent,
            "stop_cadence_on_block": policy.stop_cadence_on_block,
        }

    @staticmethod
    def _consent_snapshot(
        item: LeadCommunicationConsent,
    ) -> dict[str, object]:
        return {
            "channel": item.channel,
            "status": item.status,
            "lawful_basis": item.lawful_basis,
            "source": item.source,
            "evidence": item.evidence,
            "note": item.note,
            "granted_at": (
                item.granted_at.isoformat() if item.granted_at else None
            ),
            "revoked_at": (
                item.revoked_at.isoformat() if item.revoked_at else None
            ),
        }
