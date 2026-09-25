from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.meta_lead_ads import MetaGraphClient
from app.models import IntegrationSource
from app.repositories import (
    IntegrationSecretRepository,
    IntegrationSourceRepository,
    WorkspaceRepository,
)
from app.schemas import LeadCreate
from app.schemas.meta_integration import MetaLeadAdsConfigure
from app.security.provider_secrets import (
    ProviderSecretError,
    decrypt_provider_secret,
    encrypt_provider_secret,
)
from app.services.audit import AuditService
from app.services.integration import IntegrationService
from app.services.lead import LeadService


class MetaIntegrationError(ValueError):
    pass


class MetaIntegrationNotConfiguredError(MetaIntegrationError):
    pass


class MetaIntegrationConflictError(MetaIntegrationError):
    pass


class MetaSignatureError(MetaIntegrationError):
    pass


@dataclass(frozen=True, slots=True)
class MetaWebhookResult:
    events: int
    created: int
    updated: int
    ignored: int


class MetaLeadAdsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.sources = IntegrationSourceRepository(db)
        self.secrets = IntegrationSecretRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.integrations = IntegrationService(db)
        self.audit = AuditService(db)

    def _source(self, workspace_public_id: str, integration_public_id: str) -> IntegrationSource:
        item = self.integrations.get_source(workspace_public_id, integration_public_id)
        if item.provider != "meta":
            raise MetaIntegrationError("A fonte selecionada não é uma integração Meta.")
        return item

    def _secret_payload(self, item: IntegrationSource) -> dict[str, str]:
        stored = self.secrets.get_by_source_id(item.id)
        if stored is None:
            raise MetaIntegrationNotConfiguredError(
                "A integração Meta ainda não possui credenciais configuradas."
            )
        try:
            payload = decrypt_provider_secret(stored.encrypted_payload)
        except ProviderSecretError as exc:
            raise MetaIntegrationNotConfiguredError(str(exc)) from exc
        if not payload.get("page_access_token"):
            raise MetaIntegrationNotConfiguredError(
                "Token da página Meta não configurado."
            )
        return payload

    def server_ready(self) -> bool:
        return bool(
            self.settings.meta_app_secret.strip()
            and self.settings.meta_webhook_verify_token.strip()
        )

    def status(self, workspace_public_id: str, integration_public_id: str) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        secret = self.secrets.get_by_source_id(item.id)
        config = dict(item.provider_config or {})
        return {
            "integration_public_id": item.public_id,
            "configured": secret is not None,
            "server_ready": self.server_ready(),
            "subscribed": bool(config.get("page_subscribed", False)),
            "page_id": config.get("page_id"),
            "form_ids": list(config.get("form_ids") or []),
            "interest_field": config.get("interest_field"),
            "default_interest": config.get("default_interest"),
            "graph_api_version": self.settings.meta_graph_api_version,
            "webhook_endpoint": "/meta/webhook",
            "token_hint": config.get("token_hint"),
        }

    def configure(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        payload: MetaLeadAdsConfigure,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        for candidate in self.sources.list_active_by_provider("meta"):
            if candidate.id == item.id:
                continue
            page_id = str((candidate.provider_config or {}).get("page_id") or "")
            if page_id and page_id == payload.page_id:
                raise MetaIntegrationConflictError(
                    "Esta Página Meta já está vinculada a outra fonte do Nexyra CRM."
                )

        token_hint = (
            payload.page_access_token[-6:]
            if len(payload.page_access_token) >= 6
            else "configurado"
        )
        item.provider_config = {
            **dict(item.provider_config or {}),
            "page_id": payload.page_id,
            "form_ids": payload.form_ids,
            "interest_field": payload.interest_field,
            "default_interest": payload.default_interest,
            "token_hint": f"••••{token_hint}",
            "page_subscribed": False,
        }
        self.sources.save(item)
        self.secrets.upsert(
            integration_source_id=item.id,
            provider="meta",
            encrypted_payload=encrypt_provider_secret(
                {"page_access_token": payload.page_access_token}
            ),
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="meta_lead_ads.configured",
            after_data={
                "page_id": payload.page_id,
                "form_ids": payload.form_ids,
                "token_hint": f"••••{token_hint}",
            },
        )
        self.db.commit()
        self.db.refresh(item)
        return self.status(workspace_public_id, integration_public_id)

    def disconnect(self, workspace_public_id: str, integration_public_id: str) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        self.secrets.delete_for_source(item.id)
        item.provider_config = {
            key: value
            for key, value in dict(item.provider_config or {}).items()
            if key not in {"page_id", "form_ids", "interest_field", "default_interest", "token_hint", "page_subscribed"}
        }
        self.sources.save(item)
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="meta_lead_ads.disconnected",
        )
        self.db.commit()
        return self.status(workspace_public_id, integration_public_id)

    def subscribe_page(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        config = dict(item.provider_config or {})
        page_id = str(config.get("page_id") or "").strip()
        if not page_id:
            raise MetaIntegrationNotConfiguredError("Page ID da Meta não configurado.")
        if not self.server_ready():
            raise MetaIntegrationNotConfiguredError(
                "Configure META_APP_SECRET e META_WEBHOOK_VERIFY_TOKEN no servidor antes de assinar a página."
            )
        token = self._secret_payload(item)["page_access_token"]
        MetaGraphClient(access_token=token).subscribe_page(page_id)
        item.provider_config = {**config, "page_subscribed": True}
        self.sources.save(item)
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="meta_lead_ads.page_subscribed",
            after_data={"page_id": page_id, "field": "leadgen"},
        )
        self.db.commit()
        return {"ok": True, "page_id": page_id, "subscribed": True}

    def test_connection(self, workspace_public_id: str, integration_public_id: str) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        config = dict(item.provider_config or {})
        page_id = str(config.get("page_id") or "").strip()
        if not page_id:
            raise MetaIntegrationNotConfiguredError("Page ID da Meta não configurado.")
        token = self._secret_payload(item)["page_access_token"]
        returned_id, page_name = MetaGraphClient(access_token=token).test_page(page_id)
        return {
            "ok": True,
            "page_id": returned_id,
            "page_name": page_name,
            "graph_api_version": self.settings.meta_graph_api_version,
        }

    def verify_challenge(self, mode: str | None, token: str | None, challenge: str | None) -> str:
        expected = self.settings.meta_webhook_verify_token.strip()
        if not expected:
            raise MetaIntegrationNotConfiguredError(
                "META_WEBHOOK_VERIFY_TOKEN não configurado no servidor."
            )
        if mode != "subscribe" or token is None or not hmac.compare_digest(token, expected):
            raise MetaSignatureError("Falha na verificação do webhook da Meta.")
        return challenge or ""

    def _verify_signature(self, raw_body: bytes, signature: str | None) -> None:
        app_secret = self.settings.meta_app_secret.strip()
        if not app_secret:
            raise MetaIntegrationNotConfiguredError(
                "META_APP_SECRET não configurado no servidor."
            )
        if not signature or not signature.startswith("sha256="):
            raise MetaSignatureError("Assinatura X-Hub-Signature-256 ausente.")
        expected = hmac.new(
            app_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        received = signature.split("=", 1)[1]
        if not hmac.compare_digest(received, expected):
            raise MetaSignatureError("Assinatura do webhook da Meta inválida.")

    def _source_for_page(self, page_id: str) -> IntegrationSource | None:
        matches = [
            item
            for item in self.sources.list_active_by_provider("meta")
            if str((item.provider_config or {}).get("page_id") or "") == page_id
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _field(fields: dict[str, str], *names: str) -> str | None:
        for name in names:
            value = fields.get(name)
            if value:
                return value
        return None

    def _lead_payload(self, item: IntegrationSource, leadgen_id: str, lead) -> LeadCreate:
        config = dict(item.provider_config or {})
        fields = lead.fields
        first_name = self._field(fields, "first_name")
        last_name = self._field(fields, "last_name")
        name = self._field(fields, "full_name", "name")
        if not name and (first_name or last_name):
            name = " ".join(part for part in [first_name, last_name] if part)
        email = self._field(fields, "email")
        phone = self._field(fields, "phone_number", "phone")
        if not name:
            name = email or phone or f"Lead Meta {leadgen_id[-8:]}"

        interest_field = str(config.get("interest_field") or "").strip().lower()
        interest = fields.get(interest_field) if interest_field else None
        if not interest:
            value = config.get("default_interest")
            interest = str(value) if value else "Meta Lead Ads"

        campaign = lead.campaign_name or item.default_campaign
        message = self._field(fields, "message", "mensagem")
        return LeadCreate(
            name=name,
            phone=phone,
            email=email,
            external_id=f"meta:{leadgen_id}",
            interest=interest,
            source=item.source,
            channel=item.channel,
            campaign=campaign,
            message=message,
            consent=True,
        )

    def process_webhook(
        self,
        raw_body: bytes,
        *,
        signature: str | None,
        request_id: str | None,
        remote_ip: str | None,
    ) -> MetaWebhookResult:
        self._verify_signature(raw_body, signature)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MetaIntegrationError("Payload JSON inválido da Meta.") from exc
        if not isinstance(payload, dict) or payload.get("object") != "page":
            return MetaWebhookResult(events=0, created=0, updated=0, ignored=1)

        events = created = updated = ignored = 0
        entries = payload.get("entry")
        if not isinstance(entries, list):
            return MetaWebhookResult(events=0, created=0, updated=0, ignored=1)

        for entry in entries:
            if not isinstance(entry, dict):
                ignored += 1
                continue
            changes = entry.get("changes")
            if not isinstance(changes, list):
                ignored += 1
                continue
            for change in changes:
                if not isinstance(change, dict) or change.get("field") != "leadgen":
                    ignored += 1
                    continue
                value = change.get("value")
                if not isinstance(value, dict):
                    ignored += 1
                    continue
                page_id = str(value.get("page_id") or entry.get("id") or "")
                leadgen_id = str(value.get("leadgen_id") or "")
                form_id = str(value.get("form_id") or "")
                source = self._source_for_page(page_id)
                if source is None or not leadgen_id:
                    ignored += 1
                    continue
                allowed_forms = list((source.provider_config or {}).get("form_ids") or [])
                if allowed_forms and form_id not in allowed_forms:
                    ignored += 1
                    continue

                token = self._secret_payload(source)["page_access_token"]
                lead = MetaGraphClient(access_token=token).fetch_lead(leadgen_id)
                workspace = self.workspaces.get_by_id(source.workspace_id)
                if workspace is None:
                    ignored += 1
                    continue
                self.db.info["audit_actor_type"] = "integration"
                self.db.info.pop("audit_actor_membership_id", None)
                action, view = LeadService(self.db).intake(
                    workspace.public_id,
                    self._lead_payload(source, leadgen_id, lead),
                )
                self.integrations.record_external_intake(
                    source,
                    lead_public_id=view.lead.public_id,
                    action=action,
                    request_id=request_id,
                    idempotency_key=f"meta:{leadgen_id}",
                    remote_ip=remote_ip,
                )
                events += 1
                if action == "created":
                    created += 1
                else:
                    updated += 1
        return MetaWebhookResult(
            events=events,
            created=created,
            updated=updated,
            ignored=ignored,
        )
