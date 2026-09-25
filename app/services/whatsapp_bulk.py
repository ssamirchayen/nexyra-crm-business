from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.orm import Session

from app.models import Lead
from app.repositories import (
    IntegrationSourceRepository,
    LeadRepository,
    WorkspaceRepository,
)
from app.schemas.whatsapp_bulk import (
    WhatsAppBulkPreviewRequest,
    WhatsAppBulkSendRequest,
)
from app.security.whatsapp_confirmation import (
    create_whatsapp_confirmation,
    verify_whatsapp_confirmation,
)
from app.services.audit import AuditService
from app.services.communication_consent import CommunicationConsentService
from app.services.lead import LeadNotFoundError
from app.services.whatsapp_cloud import WhatsAppCloudService
from app.services.workspace import WorkspaceNotFoundError


class WhatsAppBulkError(ValueError):
    pass


_VARIABLE_RE = re.compile(r"{{\s*([a-z_]+)\s*}}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class BulkRecipient:
    lead: Lead
    phone: str | None
    eligible: bool
    reason: str
    parameters: list[str]
    rendered_text: str | None


class WhatsAppBulkService:
    MAX_RECIPIENTS = 25
    SUPPORTED_VARIABLES: ClassVar[set[str]] = {
        "lead_name",
        "interest",
        "phone",
        "email",
        "campaign",
        "source",
        "channel",
        "status",
        "priority",
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.leads = LeadRepository(db)
        self.sources = IntegrationSourceRepository(db)
        self.audit = AuditService(db)
        self.consent = CommunicationConsentService(db)
        self.whatsapp = WhatsAppCloudService(db)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(f"Empresa não encontrada: {public_id}")
        return workspace

    def source_options(self, workspace_public_id: str) -> list[dict[str, str]]:
        workspace = self._workspace(workspace_public_id)
        return [
            {"public_id": item.public_id, "name": item.name}
            for item in self.sources.list_for_workspace(workspace.id)
            if item.provider == "whatsapp" and item.active
        ]

    def _template_descriptor(
        self,
        workspace_public_id: str,
        payload: WhatsAppBulkPreviewRequest,
    ) -> dict[str, object]:
        templates = self.whatsapp.list_templates(
            workspace_public_id,
            payload.integration_public_id,
            limit=100,
        )
        selected = next(
            (
                item
                for item in templates
                if item["name"] == payload.template_name
                and item["language"] == payload.language_code
            ),
            None,
        )
        if selected is None:
            raise WhatsAppBulkError(
                "Template aprovado não encontrado para o nome e idioma informados."
            )
        if not bool(selected.get("supported", False)):
            raise WhatsAppBulkError(
                str(selected.get("unsupported_reason") or "Template não suportado.")
            )
        expected = int(selected.get("parameter_count") or 0)
        if len(payload.parameter_templates) != expected:
            raise WhatsAppBulkError(
                f"Este template exige {expected} parâmetro(s); "
                f"foram configurados {len(payload.parameter_templates)}."
            )
        return selected

    @classmethod
    def _render_parameter(cls, template: str, lead: Lead) -> str:
        values = {
            "lead_name": lead.name,
            "interest": lead.interest or "",
            "phone": lead.phone or "",
            "email": lead.email or "",
            "campaign": lead.campaign or "",
            "source": lead.source,
            "channel": lead.channel,
            "status": lead.status,
            "priority": lead.priority,
        }
        unknown = {
            match.group(1).lower()
            for match in _VARIABLE_RE.finditer(template)
            if match.group(1).lower() not in cls.SUPPORTED_VARIABLES
        }
        if unknown:
            names = ", ".join(sorted(unknown))
            raise WhatsAppBulkError(f"Variável(is) não suportada(s): {names}.")

        def replace(match: re.Match[str]) -> str:
            return str(values[match.group(1).lower()])

        rendered = _VARIABLE_RE.sub(replace, template).strip()
        if not rendered:
            raise WhatsAppBulkError(
                f"Um parâmetro ficou vazio para o lead {lead.name}."
            )
        return rendered

    @staticmethod
    def _render_body(body_text: str | None, parameters: list[str]) -> str:
        rendered = body_text or ""
        for index, value in enumerate(parameters, start=1):
            rendered = re.sub(
                rf"{{{{\s*{index}\s*}}}}",
                lambda _match, replacement=value: replacement,
                rendered,
            )
        return rendered or "[Template WhatsApp]"

    def _lead(self, workspace_id: int, public_id: str) -> Lead:
        lead = self.leads.get_by_public_id(
            workspace_id=workspace_id,
            public_id=public_id,
        )
        if lead is None:
            raise LeadNotFoundError(f"Lead não encontrado: {public_id}")
        return lead

    def _recipient(
        self,
        lead: Lead,
        *,
        parameter_templates: list[str],
        body_text: str | None,
    ) -> BulkRecipient:
        phone = lead.normalized_phone or "".join(
            char for char in (lead.phone or "") if char.isdigit()
        )
        if not lead.active:
            return BulkRecipient(
                lead=lead,
                phone=phone or None,
                eligible=False,
                reason="Lead inativo.",
                parameters=[],
                rendered_text=None,
            )
        if not phone:
            return BulkRecipient(
                lead=lead,
                phone=None,
                eligible=False,
                reason="Lead sem número de WhatsApp.",
                parameters=[],
                rendered_text=None,
            )
        eligibility = self.consent.eligibility_for_lead(lead, "whatsapp")
        if not eligibility.allowed:
            return BulkRecipient(
                lead=lead,
                phone=phone,
                eligible=False,
                reason=f"Bloqueado: {eligibility.reason}.",
                parameters=[],
                rendered_text=None,
            )
        try:
            parameters = [
                self._render_parameter(value, lead)
                for value in parameter_templates
            ]
        except WhatsAppBulkError as exc:
            return BulkRecipient(
                lead=lead,
                phone=phone,
                eligible=False,
                reason=str(exc),
                parameters=[],
                rendered_text=None,
            )
        return BulkRecipient(
            lead=lead,
            phone=phone,
            eligible=True,
            reason="Elegível para envio.",
            parameters=parameters,
            rendered_text=self._render_body(body_text, parameters),
        )

    def _build(
        self,
        workspace_public_id: str,
        payload: WhatsAppBulkPreviewRequest,
    ) -> tuple[object, dict[str, object], list[BulkRecipient], str]:
        if len(payload.lead_public_ids) > self.MAX_RECIPIENTS:
            raise WhatsAppBulkError(
                f"O limite é de {self.MAX_RECIPIENTS} leads por envio em lote."
            )
        workspace = self._workspace(workspace_public_id)
        source = self.whatsapp._source(
            workspace_public_id,
            payload.integration_public_id,
        )
        if not source.active:
            raise WhatsAppBulkError("A integração WhatsApp selecionada está inativa.")
        descriptor = self._template_descriptor(workspace_public_id, payload)
        recipients = [
            self._recipient(
                self._lead(workspace.id, public_id),
                parameter_templates=payload.parameter_templates,
                body_text=(
                    str(descriptor.get("body_text"))
                    if descriptor.get("body_text") is not None
                    else None
                ),
            )
            for public_id in payload.lead_public_ids
        ]
        canonical = json.dumps(
            {
                "integration_public_id": payload.integration_public_id,
                "template_name": payload.template_name,
                "language_code": payload.language_code,
                "parameter_templates": payload.parameter_templates,
                "body_text": descriptor.get("body_text"),
                "recipients": [
                    {
                        "lead_public_id": item.lead.public_id,
                        "phone": item.phone,
                        "eligible": item.eligible,
                        "parameters": item.parameters,
                    }
                    for item in recipients
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return source, descriptor, recipients, fingerprint

    def preview(
        self,
        workspace_public_id: str,
        payload: WhatsAppBulkPreviewRequest,
    ) -> dict[str, object]:
        _, _, recipients, fingerprint = self._build(
            workspace_public_id,
            payload,
        )
        token, expires_at = create_whatsapp_confirmation(
            integration_public_id=payload.integration_public_id,
            to="bulk",
            text=fingerprint,
            ttl_seconds=300,
        )
        eligible = sum(1 for item in recipients if item.eligible)
        return {
            "requested": len(recipients),
            "eligible": eligible,
            "blocked": len(recipients) - eligible,
            "integration_public_id": payload.integration_public_id,
            "template_name": payload.template_name,
            "language_code": payload.language_code,
            "parameter_templates": payload.parameter_templates,
            "confirmation_token": token,
            "expires_at": expires_at,
            "recipients": [self._recipient_dict(item) for item in recipients],
        }

    def send(
        self,
        workspace_public_id: str,
        payload: WhatsAppBulkSendRequest,
    ) -> dict[str, object]:
        source, _, recipients, fingerprint = self._build(
            workspace_public_id,
            payload,
        )
        verify_whatsapp_confirmation(
            payload.confirmation_token,
            integration_public_id=payload.integration_public_id,
            to="bulk",
            text=fingerprint,
        )
        eligible = [item for item in recipients if item.eligible]
        if not eligible:
            raise WhatsAppBulkError("Nenhum lead elegível para o envio em lote.")

        items: list[dict[str, object]] = []
        sent = 0
        failed = 0
        for recipient in recipients:
            if not recipient.eligible:
                items.append(
                    {
                        "lead_public_id": recipient.lead.public_id,
                        "lead_name": recipient.lead.name,
                        "phone": recipient.phone,
                        "status": "blocked",
                        "provider_message_id": None,
                        "error": recipient.reason,
                    }
                )
                continue
            try:
                result = self.whatsapp._send_template_prepared(
                    source,
                    to=recipient.phone or "",
                    template_name=payload.template_name,
                    language_code=payload.language_code,
                    parameters=recipient.parameters,
                    rendered=recipient.rendered_text or "",
                )
                sent += 1
                items.append(
                    {
                        "lead_public_id": recipient.lead.public_id,
                        "lead_name": recipient.lead.name,
                        "phone": recipient.phone,
                        "status": "sent",
                        "provider_message_id": result["provider_message_id"],
                        "error": None,
                    }
                )
            except ValueError as exc:
                failed += 1
                items.append(
                    {
                        "lead_public_id": recipient.lead.public_id,
                        "lead_name": recipient.lead.name,
                        "phone": recipient.phone,
                        "status": "failed",
                        "provider_message_id": None,
                        "error": str(exc),
                    }
                )

        self.audit.record(
            workspace_id=source.workspace_id,
            entity_type="integration_source",
            entity_public_id=source.public_id,
            action="whatsapp.bulk_template_completed",
            after_data={
                "requested": len(recipients),
                "attempted": len(eligible),
                "sent": sent,
                "failed": failed,
                "blocked": len(recipients) - len(eligible),
                "template_name": payload.template_name,
                "language_code": payload.language_code,
            },
        )
        self.db.commit()
        return {
            "requested": len(recipients),
            "attempted": len(eligible),
            "sent": sent,
            "failed": failed,
            "blocked": len(recipients) - len(eligible),
            "items": items,
        }

    @staticmethod
    def _recipient_dict(item: BulkRecipient) -> dict[str, object]:
        return {
            "lead_public_id": item.lead.public_id,
            "lead_name": item.lead.name,
            "phone": item.phone,
            "eligible": item.eligible,
            "reason": item.reason,
            "parameters": item.parameters,
            "rendered_text": item.rendered_text,
        }