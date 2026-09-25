from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.audit import activity_snapshot
from app.core.config import get_settings
from app.integrations.whatsapp_cloud import WhatsAppGraphClient, WhatsAppTemplateInfo
from app.models import IntegrationSource, WhatsAppMessage
from app.repositories import (
    ActivityRepository,
    IntegrationSecretRepository,
    IntegrationSourceRepository,
    LeadRepository,
    WhatsAppMessageRepository,
)
from app.schemas import LeadCreate
from app.schemas.whatsapp_integration import (
    WhatsAppConfigure,
    WhatsAppEmbeddedSignupComplete,
    WhatsAppEmbeddedSignupSelectPhone,
)
from app.security.provider_secrets import (
    ProviderSecretError,
    decrypt_provider_secret,
    encrypt_provider_secret,
)
from app.security.whatsapp_confirmation import (
    create_whatsapp_confirmation,
    verify_whatsapp_confirmation,
)
from app.services.audit import AuditService
from app.services.communication_consent import CommunicationConsentService
from app.services.integration import IntegrationService
from app.services.lead import LeadService


class WhatsAppIntegrationError(ValueError):
    pass


class WhatsAppNotConfiguredError(WhatsAppIntegrationError):
    pass


class WhatsAppIntegrationConflictError(WhatsAppIntegrationError):
    pass


class WhatsAppSignatureError(WhatsAppIntegrationError):
    pass


@dataclass(frozen=True, slots=True)
class WhatsAppWebhookResult:
    messages: int
    statuses: int
    created: int
    updated: int
    ignored: int
    echoes: int = 0
    history_events: int = 0
    contact_sync_events: int = 0


_TEMPLATE_PARAMETER_RE = re.compile(r"{{\s*(\d+)\s*}}")


class WhatsAppCloudService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.sources = IntegrationSourceRepository(db)
        self.secrets = IntegrationSecretRepository(db)
        self.messages = WhatsAppMessageRepository(db)
        self.leads = LeadRepository(db)
        self.activities = ActivityRepository(db)
        self.integrations = IntegrationService(db)
        self.audit = AuditService(db)

    def _source(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> IntegrationSource:
        item = self.integrations.get_source(
            workspace_public_id,
            integration_public_id,
        )
        if item.provider != "whatsapp":
            raise WhatsAppIntegrationError(
                "A fonte selecionada não é uma integração WhatsApp."
            )
        return item

    def _secret_payload(self, item: IntegrationSource) -> dict[str, str]:
        stored = self.secrets.get_by_source_id(item.id)
        if stored is None:
            raise WhatsAppNotConfiguredError(
                "A integração WhatsApp ainda não possui credenciais configuradas."
            )
        try:
            payload = decrypt_provider_secret(stored.encrypted_payload)
        except ProviderSecretError as exc:
            raise WhatsAppNotConfiguredError(str(exc)) from exc
        if not payload.get("access_token"):
            raise WhatsAppNotConfiguredError(
                "Access Token do WhatsApp não configurado."
            )
        return payload

    def server_ready(self) -> bool:
        return bool(
            self.settings.whatsapp_app_secret.strip()
            and self.settings.whatsapp_webhook_verify_token.strip()
        )

    def _embedded_app_id(self) -> str:
        return (
            self.settings.whatsapp_meta_app_id.strip()
            or self.settings.meta_app_id.strip()
        )

    def embedded_signup_config(self) -> dict[str, object]:
        app_id = self._embedded_app_id()
        config_id = self.settings.whatsapp_embedded_signup_config_id.strip()
        app_secret = self.settings.whatsapp_app_secret.strip()
        return {
            "enabled": bool(app_id and config_id and app_secret),
            "app_id": app_id or None,
            "config_id": config_id or None,
            "graph_api_version": self.settings.whatsapp_graph_api_version,
            "feature_type": "whatsapp_business_app_onboarding",
            "required_webhook_fields": [
                "messages",
                "history",
                "smb_app_state_sync",
                "smb_message_echoes",
            ],
        }

    def _ensure_phone_available(
        self,
        item: IntegrationSource,
        phone_number_id: str,
    ) -> None:
        for candidate in self.sources.list_active_by_provider("whatsapp"):
            if candidate.id == item.id:
                continue
            configured = str(
                (candidate.provider_config or {}).get("phone_number_id") or ""
            ).strip()
            if configured and configured == phone_number_id:
                raise WhatsAppIntegrationConflictError(
                    "Este Phone Number ID já está vinculado a outra fonte do Nexyra CRM."
                )

    @staticmethod
    def _phone_candidate_payload(info: object) -> dict[str, object]:
        return {
            "phone_number_id": info.phone_number_id,
            "display_phone_number": info.display_phone_number,
            "verified_name": info.verified_name,
            "quality_rating": info.quality_rating,
        }

    def _finalize_embedded_signup(
        self,
        *,
        item: IntegrationSource,
        access_token: str,
        business_account_id: str,
        phone_number_id: str,
        default_interest: str | None,
        event: str | None,
    ) -> dict[str, object]:
        self._ensure_phone_available(item, phone_number_id)
        client = WhatsAppGraphClient(access_token=access_token)
        info = client.test_phone_number(phone_number_id)
        client.subscribe_business_account(business_account_id)

        token_hint = (
            access_token[-6:] if len(access_token) >= 6 else "configurado"
        )
        previous = dict(item.provider_config or {})
        item.provider_config = {
            **previous,
            "phone_number_id": info.phone_number_id,
            "business_account_id": business_account_id,
            "display_phone_number": info.display_phone_number,
            "verified_name": info.verified_name,
            "default_interest": default_interest or "WhatsApp",
            "token_hint": f"••••{token_hint}",
            "webhook_subscribed": True,
            "onboarding_mode": "embedded_signup_coexistence",
            "coexistence": True,
            "embedded_signup_connected": True,
            "embedded_signup_event": event,
            "embedded_signup_pending_phone_ids": [],
        }
        self.sources.save(item)
        self.secrets.upsert(
            integration_source_id=item.id,
            provider="whatsapp",
            encrypted_payload=encrypt_provider_secret(
                {"access_token": access_token}
            ),
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="whatsapp_coexistence.connected",
            after_data={
                "phone_number_id": info.phone_number_id,
                "business_account_id": business_account_id,
                "display_phone_number": info.display_phone_number,
                "verified_name": info.verified_name,
                "onboarding_mode": "embedded_signup_coexistence",
                "webhook_subscribed": True,
            },
        )
        self.db.commit()
        self.db.refresh(item)
        return {
            "ok": True,
            "connected": True,
            "selection_required": False,
            "business_account_id": business_account_id,
            "phone_number_id": info.phone_number_id,
            "display_phone_number": info.display_phone_number,
            "verified_name": info.verified_name,
            "subscribed": True,
            "coexistence": True,
            "candidates": [],
        }

    def complete_embedded_signup(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        payload: WhatsAppEmbeddedSignupComplete,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        embedded = self.embedded_signup_config()
        if not embedded["enabled"]:
            raise WhatsAppNotConfiguredError(
                "Configure WHATSAPP_META_APP_ID, WHATSAPP_APP_SECRET e "
                "WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID no servidor."
            )

        app_id = str(embedded["app_id"])
        app_secret = self.settings.whatsapp_app_secret.strip()
        access_token = WhatsAppGraphClient.exchange_embedded_signup_code(
            code=payload.code,
            app_id=app_id,
            app_secret=app_secret,
        )

        business_account_id = (payload.waba_id or "").strip()
        if not business_account_id:
            waba_ids = WhatsAppGraphClient.discover_waba_ids(
                user_access_token=access_token,
                app_id=app_id,
                app_secret=app_secret,
            )
            if len(waba_ids) != 1:
                raise WhatsAppIntegrationConflictError(
                    "Não foi possível identificar de forma única a conta WhatsApp "
                    "compartilhada. Conclua novamente o Embedded Signup."
                )
            business_account_id = waba_ids[0]

        client = WhatsAppGraphClient(access_token=access_token)
        candidates = client.list_phone_numbers(business_account_id)
        if not candidates:
            raise WhatsAppIntegrationError(
                "A conta WhatsApp compartilhada não retornou números disponíveis."
            )

        requested_phone_id = (payload.phone_number_id or "").strip()
        if requested_phone_id:
            matching = [
                info
                for info in candidates
                if info.phone_number_id == requested_phone_id
            ]
            if not matching:
                raise WhatsAppIntegrationConflictError(
                    "O Phone Number ID informado não pertence à conta WhatsApp compartilhada."
                )
            chosen = matching[0]
        elif len(candidates) == 1:
            chosen = candidates[0]
        else:
            client.subscribe_business_account(business_account_id)
            token_hint = (
                access_token[-6:]
                if len(access_token) >= 6
                else "configurado"
            )
            previous = dict(item.provider_config or {})
            item.provider_config = {
                **previous,
                "business_account_id": business_account_id,
                "default_interest": payload.default_interest or "WhatsApp",
                "token_hint": f"••••{token_hint}",
                "webhook_subscribed": True,
                "onboarding_mode": "embedded_signup_coexistence_pending",
                "coexistence": True,
                "embedded_signup_connected": False,
                "embedded_signup_event": payload.event,
                "embedded_signup_pending_phone_ids": [
                    info.phone_number_id for info in candidates
                ],
            }
            self.sources.save(item)
            self.secrets.upsert(
                integration_source_id=item.id,
                provider="whatsapp",
                encrypted_payload=encrypt_provider_secret(
                    {"access_token": access_token}
                ),
            )
            self.audit.record(
                workspace_id=item.workspace_id,
                entity_type="integration_source",
                entity_public_id=item.public_id,
                action="whatsapp_coexistence.phone_selection_required",
                after_data={
                    "business_account_id": business_account_id,
                    "phone_candidates": [
                        info.phone_number_id for info in candidates
                    ],
                },
            )
            self.db.commit()
            return {
                "ok": True,
                "connected": False,
                "selection_required": True,
                "business_account_id": business_account_id,
                "phone_number_id": None,
                "display_phone_number": None,
                "verified_name": None,
                "subscribed": True,
                "coexistence": True,
                "candidates": [
                    self._phone_candidate_payload(info)
                    for info in candidates
                ],
            }

        return self._finalize_embedded_signup(
            item=item,
            access_token=access_token,
            business_account_id=business_account_id,
            phone_number_id=chosen.phone_number_id,
            default_interest=payload.default_interest,
            event=payload.event,
        )

    def select_embedded_signup_phone(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        payload: WhatsAppEmbeddedSignupSelectPhone,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        config = dict(item.provider_config or {})
        business_account_id = str(
            config.get("business_account_id") or ""
        ).strip()
        pending_ids = {
            str(value)
            for value in (
                config.get("embedded_signup_pending_phone_ids") or []
            )
        }
        if (
            config.get("onboarding_mode")
            != "embedded_signup_coexistence_pending"
            or not business_account_id
        ):
            raise WhatsAppIntegrationConflictError(
                "Não há uma seleção de número pendente para esta integração."
            )
        if payload.phone_number_id not in pending_ids:
            raise WhatsAppIntegrationConflictError(
                "O Phone Number ID não está entre os números autorizados no Embedded Signup."
            )
        access_token = self._secret_payload(item)["access_token"]
        return self._finalize_embedded_signup(
            item=item,
            access_token=access_token,
            business_account_id=business_account_id,
            phone_number_id=payload.phone_number_id,
            default_interest=payload.default_interest
            or str(config.get("default_interest") or "WhatsApp"),
            event=str(config.get("embedded_signup_event") or "") or None,
        )

    def request_coexistence_sync(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        sync_type: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        config = dict(item.provider_config or {})
        if not bool(config.get("coexistence")):
            raise WhatsAppIntegrationConflictError(
                "Esta integração não foi conectada em modo de coexistência."
            )
        phone_number_id = str(config.get("phone_number_id") or "").strip()
        if not phone_number_id:
            raise WhatsAppNotConfiguredError(
                "Phone Number ID do WhatsApp não configurado."
            )
        token = self._secret_payload(item)["access_token"]
        request_id = WhatsAppGraphClient(
            access_token=token
        ).request_business_app_sync(
            phone_number_id=phone_number_id,
            sync_type=sync_type,
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="whatsapp_coexistence.sync_requested",
            after_data={
                "sync_type": sync_type,
                "request_id": request_id,
            },
        )
        self.db.commit()
        return {
            "ok": True,
            "sync_type": sync_type,
            "request_id": request_id,
        }

    def status(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        secret = self.secrets.get_by_source_id(item.id)
        config = dict(item.provider_config or {})
        return {
            "integration_public_id": item.public_id,
            "configured": secret is not None,
            "server_ready": self.server_ready(),
            "subscribed": bool(config.get("webhook_subscribed", False)),
            "phone_number_id": config.get("phone_number_id"),
            "business_account_id": config.get("business_account_id"),
            "display_phone_number": config.get("display_phone_number"),
            "verified_name": config.get("verified_name"),
            "default_interest": config.get("default_interest"),
            "graph_api_version": self.settings.whatsapp_graph_api_version,
            "webhook_endpoint": "/whatsapp/webhook",
            "token_hint": config.get("token_hint"),
            "recent_messages": len(
                self.messages.recent_for_source(
                    integration_source_id=item.id,
                    limit=20,
                )
            ),
            "onboarding_mode": config.get("onboarding_mode"),
            "coexistence": bool(config.get("coexistence", False)),
            "embedded_signup_connected": bool(
                config.get("embedded_signup_connected", False)
            ),
        }

    def configure(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        payload: WhatsAppConfigure,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        self._ensure_phone_available(item, payload.phone_number_id)

        token_hint = (
            payload.access_token[-6:]
            if len(payload.access_token) >= 6
            else "configurado"
        )
        previous = dict(item.provider_config or {})
        item.provider_config = {
            **previous,
            "phone_number_id": payload.phone_number_id,
            "business_account_id": payload.business_account_id,
            "default_interest": payload.default_interest,
            "token_hint": f"••••{token_hint}",
            "webhook_subscribed": False,
            "onboarding_mode": "manual",
            "coexistence": False,
            "embedded_signup_connected": False,
            "embedded_signup_pending_phone_ids": [],
        }
        self.sources.save(item)
        self.secrets.upsert(
            integration_source_id=item.id,
            provider="whatsapp",
            encrypted_payload=encrypt_provider_secret(
                {"access_token": payload.access_token}
            ),
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="whatsapp_cloud.configured",
            after_data={
                "phone_number_id": payload.phone_number_id,
                "business_account_id": payload.business_account_id,
                "token_hint": f"••••{token_hint}",
            },
        )
        self.db.commit()
        self.db.refresh(item)
        return self.status(workspace_public_id, integration_public_id)

    def disconnect(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        self.secrets.delete_for_source(item.id)
        removable = {
            "phone_number_id",
            "business_account_id",
            "display_phone_number",
            "verified_name",
            "default_interest",
            "token_hint",
            "webhook_subscribed",
            "onboarding_mode",
            "coexistence",
            "embedded_signup_connected",
            "embedded_signup_event",
            "embedded_signup_pending_phone_ids",
        }
        item.provider_config = {
            key: value
            for key, value in dict(item.provider_config or {}).items()
            if key not in removable
        }
        self.sources.save(item)
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="whatsapp_cloud.disconnected",
        )
        self.db.commit()
        return self.status(workspace_public_id, integration_public_id)

    def test_connection(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        config = dict(item.provider_config or {})
        phone_number_id = str(config.get("phone_number_id") or "").strip()
        if not phone_number_id:
            raise WhatsAppNotConfiguredError(
                "Phone Number ID do WhatsApp não configurado."
            )
        token = self._secret_payload(item)["access_token"]
        info = WhatsAppGraphClient(access_token=token).test_phone_number(
            phone_number_id
        )
        item.provider_config = {
            **config,
            "display_phone_number": info.display_phone_number,
            "verified_name": info.verified_name,
        }
        self.sources.save(item)
        self.db.commit()
        return {
            "ok": True,
            "phone_number_id": info.phone_number_id,
            "display_phone_number": info.display_phone_number,
            "verified_name": info.verified_name,
            "quality_rating": info.quality_rating,
            "graph_api_version": self.settings.whatsapp_graph_api_version,
        }

    def subscribe_business_account(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        config = dict(item.provider_config or {})
        business_account_id = str(
            config.get("business_account_id") or ""
        ).strip()
        if not business_account_id:
            raise WhatsAppNotConfiguredError(
                "WhatsApp Business Account ID não configurado."
            )
        if not self.server_ready():
            raise WhatsAppNotConfiguredError(
                "Configure WHATSAPP_APP_SECRET e WHATSAPP_WEBHOOK_VERIFY_TOKEN "
                "no servidor antes de assinar a conta."
            )
        token = self._secret_payload(item)["access_token"]
        WhatsAppGraphClient(
            access_token=token
        ).subscribe_business_account(business_account_id)
        item.provider_config = {**config, "webhook_subscribed": True}
        self.sources.save(item)
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="whatsapp_cloud.webhook_subscribed",
            after_data={"business_account_id": business_account_id},
        )
        self.db.commit()
        return {
            "ok": True,
            "business_account_id": business_account_id,
            "subscribed": True,
        }

    def verify_challenge(
        self,
        mode: str | None,
        token: str | None,
        challenge: str | None,
    ) -> str:
        expected = self.settings.whatsapp_webhook_verify_token.strip()
        if not expected:
            raise WhatsAppNotConfiguredError(
                "WHATSAPP_WEBHOOK_VERIFY_TOKEN não configurado no servidor."
            )
        if (
            mode != "subscribe"
            or token is None
            or not hmac.compare_digest(token, expected)
        ):
            raise WhatsAppSignatureError(
                "Falha na verificação do webhook do WhatsApp."
            )
        return challenge or ""

    def _verify_signature(
        self,
        raw_body: bytes,
        signature: str | None,
    ) -> None:
        app_secret = self.settings.whatsapp_app_secret.strip()
        if not app_secret:
            raise WhatsAppNotConfiguredError(
                "WHATSAPP_APP_SECRET não configurado no servidor."
            )
        if not signature or not signature.startswith("sha256="):
            raise WhatsAppSignatureError(
                "Assinatura X-Hub-Signature-256 ausente."
            )
        expected = hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        received = signature.split("=", 1)[1]
        if not hmac.compare_digest(received, expected):
            raise WhatsAppSignatureError(
                "Assinatura do webhook do WhatsApp inválida."
            )

    def _source_for_phone_number_id(
        self,
        phone_number_id: str,
    ) -> IntegrationSource | None:
        for item in self.sources.list_active_by_provider("whatsapp"):
            configured = str(
                (item.provider_config or {}).get("phone_number_id") or ""
            )
            if configured == phone_number_id:
                return item
        return None

    def _source_for_business_account_id(
        self,
        business_account_id: str,
    ) -> IntegrationSource | None:
        for item in self.sources.list_active_by_provider("whatsapp"):
            configured = str(
                (item.provider_config or {}).get("business_account_id") or ""
            )
            if configured == business_account_id:
                return item
        return None

    @staticmethod
    def _provider_timestamp(value: object) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(int(str(value)), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _message_body(message: dict[str, Any]) -> tuple[str, str | None]:
        message_type = str(message.get("type") or "unknown")
        if message_type == "text":
            text = message.get("text")
            if isinstance(text, dict) and text.get("body") is not None:
                return message_type, str(text["body"]).strip()
        if message_type == "button":
            button = message.get("button")
            if isinstance(button, dict):
                value = button.get("text") or button.get("payload")
                if value is not None:
                    return message_type, str(value).strip()
        if message_type == "interactive":
            interactive = message.get("interactive")
            if isinstance(interactive, dict):
                for key in ("button_reply", "list_reply"):
                    reply = interactive.get(key)
                    if isinstance(reply, dict):
                        value = reply.get("title") or reply.get("id")
                        if value is not None:
                            return message_type, str(value).strip()
        if message_type == "location":
            location = message.get("location")
            if isinstance(location, dict):
                latitude = location.get("latitude")
                longitude = location.get("longitude")
                return message_type, f"Localização: {latitude}, {longitude}"
        media = message.get(message_type)
        if isinstance(media, dict) and media.get("caption"):
            return message_type, str(media["caption"]).strip()
        return message_type, f"[{message_type}]"

    def _record_completed_activity(
        self,
        *,
        item: IntegrationSource,
        lead_id: int | None,
        lead_public_id: str | None,
        direction: str,
        body: str | None,
        actor_type: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        title = (
            "WhatsApp recebido"
            if direction == "inbound"
            else "WhatsApp enviado"
        )
        activity = self.activities.create(
            workspace_id=item.workspace_id,
            lead_id=lead_id,
            opportunity_id=None,
            owner_membership_id=None,
            activity_type="whatsapp",
            title=title,
            description=body,
            status="completed",
            due_at=None,
            completed_at=now,
            cancelled_at=None,
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="activity",
            entity_public_id=activity.public_id,
            action="activity.completed",
            actor_type=actor_type,
            after_data=activity_snapshot(
                activity,
                lead_public_id=lead_public_id,
                opportunity_public_id=None,
                owner_user_public_id=None,
            ),
        )

    def _handle_inbound_message(
        self,
        *,
        item: IntegrationSource,
        message: dict[str, Any],
        contact_names: dict[str, str],
        business_phone: str | None,
    ) -> tuple[str, WhatsAppMessage | None]:
        provider_message_id = str(message.get("id") or "").strip()
        sender = "".join(
            char for char in str(message.get("from") or "") if char.isdigit()
        )
        if not provider_message_id or not sender:
            return "ignored", None
        if self.messages.get_by_provider_message_id(provider_message_id):
            return "ignored", None

        message_type, body = self._message_body(message)
        profile_name = contact_names.get(sender)
        lead_name = profile_name or f"WhatsApp {sender[-8:]}"
        config = dict(item.provider_config or {})
        action, lead_view = LeadService(self.db).intake(
            self._workspace_public_id(item),
            LeadCreate(
                name=lead_name,
                phone=sender,
                interest=(
                    str(config.get("default_interest"))
                    if config.get("default_interest")
                    else "WhatsApp"
                ),
                source=item.source,
                channel=item.channel,
                campaign=item.default_campaign,
                message=body,
                priority="media",
                consent=True,
            ),
        )
        lead = lead_view.lead
        stored = self.messages.create(
            workspace_id=item.workspace_id,
            integration_source_id=item.id,
            lead_id=lead.id,
            provider_message_id=provider_message_id,
            direction="inbound",
            message_type=message_type,
            from_phone=sender,
            to_phone=business_phone,
            body=body,
            status="received",
            provider_timestamp=self._provider_timestamp(message.get("timestamp")),
            metadata_json={
                "context": message.get("context"),
                "referral": message.get("referral"),
            },
        )
        item.intake_count += 1
        item.last_intake_at = datetime.now(timezone.utc)
        self.sources.save(item)
        self._record_completed_activity(
            item=item,
            lead_id=lead.id,
            lead_public_id=lead.public_id,
            direction="inbound",
            body=body,
            actor_type="integration",
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="whatsapp_message",
            entity_public_id=stored.public_id,
            action="whatsapp.message_received",
            actor_type="integration",
            after_data={
                "lead_public_id": lead.public_id,
                "provider_message_id": provider_message_id,
                "from": sender,
                "message_type": message_type,
                "lead_action": action,
            },
        )
        self.db.commit()
        return action, stored

    def _handle_message_echo(
        self,
        *,
        item: IntegrationSource,
        message: dict[str, Any],
        business_phone: str | None,
    ) -> tuple[str, WhatsAppMessage | None]:
        provider_message_id = str(message.get("id") or "").strip()
        recipient = "".join(
            char for char in str(message.get("to") or "") if char.isdigit()
        )
        if not provider_message_id or not recipient:
            return "ignored", None
        if self.messages.get_by_provider_message_id(provider_message_id):
            return "ignored", None

        message_type, body = self._message_body(message)
        config = dict(item.provider_config or {})
        lead = self.leads.find_duplicate(
            workspace_id=item.workspace_id,
            normalized_phone=recipient,
            normalized_email=None,
            external_id=None,
        )
        if lead is None:
            lead_view = LeadService(self.db).create(
                self._workspace_public_id(item),
                LeadCreate(
                    name=f"WhatsApp {recipient[-8:]}",
                    phone=recipient,
                    interest=(
                        str(config.get("default_interest"))
                        if config.get("default_interest")
                        else "WhatsApp"
                    ),
                    source=item.source,
                    channel=item.channel,
                    campaign=item.default_campaign,
                    message=body,
                    priority="media",
                    consent=False,
                ),
            )
            lead = lead_view.lead
            action = "created"
        else:
            action = "duplicate_kept"
        stored = self.messages.create(
            workspace_id=item.workspace_id,
            integration_source_id=item.id,
            lead_id=lead.id,
            provider_message_id=provider_message_id,
            direction="outbound",
            message_type=message_type,
            from_phone=business_phone,
            to_phone=recipient,
            body=body,
            status="sent_from_business_app",
            provider_timestamp=self._provider_timestamp(message.get("timestamp")),
            metadata_json={
                "coexistence": True,
                "source": "whatsapp_business_app",
            },
        )
        self._record_completed_activity(
            item=item,
            lead_id=lead.id,
            lead_public_id=lead.public_id,
            direction="outbound",
            body=body,
            actor_type="integration",
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="whatsapp_message",
            entity_public_id=stored.public_id,
            action="whatsapp_coexistence.message_echo_received",
            actor_type="integration",
            after_data={
                "lead_public_id": lead.public_id,
                "provider_message_id": provider_message_id,
                "to": recipient,
                "message_type": message_type,
                "lead_action": action,
            },
        )
        self.db.commit()
        return action, stored

    def _workspace_public_id(self, item: IntegrationSource) -> str:
        workspace = self.integrations.workspaces.get_by_id(item.workspace_id)
        if workspace is None:
            raise WhatsAppIntegrationError(
                "Workspace da integração WhatsApp não encontrado."
            )
        return workspace.public_id

    def _handle_status(
        self,
        *,
        status_payload: dict[str, Any],
    ) -> bool:
        provider_message_id = str(status_payload.get("id") or "").strip()
        if not provider_message_id:
            return False
        stored = self.messages.get_by_provider_message_id(provider_message_id)
        if stored is None:
            return False
        stored.status = str(status_payload.get("status") or stored.status)
        stored.provider_timestamp = self._provider_timestamp(
            status_payload.get("timestamp")
        ) or stored.provider_timestamp
        errors = status_payload.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            first_error = errors[0]
            if first_error.get("code") is not None:
                stored.error_code = str(first_error["code"])
            if first_error.get("message") is not None:
                stored.error_message = str(first_error["message"])
        self.messages.save(stored)
        self.audit.record(
            workspace_id=stored.workspace_id,
            entity_type="whatsapp_message",
            entity_public_id=stored.public_id,
            action="whatsapp.message_status_updated",
            actor_type="integration",
            after_data={
                "provider_message_id": provider_message_id,
                "status": stored.status,
                "error_code": stored.error_code,
            },
        )
        self.db.commit()
        return True

    def handle_webhook(
        self,
        *,
        raw_body: bytes,
        signature: str | None,
    ) -> WhatsAppWebhookResult:
        self._verify_signature(raw_body, signature)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WhatsAppIntegrationError(
                "Payload inválido no webhook do WhatsApp."
            ) from exc
        if not isinstance(payload, dict):
            raise WhatsAppIntegrationError(
                "Payload inválido no webhook do WhatsApp."
            )
        if payload.get("object") != "whatsapp_business_account":
            return WhatsAppWebhookResult(0, 0, 0, 0, 1)

        messages_count = 0
        statuses_count = 0
        created = 0
        updated = 0
        ignored = 0
        echoes_count = 0
        history_events = 0
        contact_sync_events = 0
        entries = payload.get("entry")
        if not isinstance(entries, list):
            return WhatsAppWebhookResult(0, 0, 0, 0, 1)

        for entry in entries:
            if not isinstance(entry, dict):
                ignored += 1
                continue
            entry_waba_id = str(entry.get("id") or "").strip()
            changes = entry.get("changes")
            if not isinstance(changes, list):
                ignored += 1
                continue
            for change in changes:
                if not isinstance(change, dict):
                    ignored += 1
                    continue
                field = str(change.get("field") or "").strip()
                value = change.get("value")
                if not isinstance(value, dict):
                    ignored += 1
                    continue

                metadata = value.get("metadata")
                phone_number_id = ""
                business_phone: str | None = None
                if isinstance(metadata, dict):
                    phone_number_id = str(
                        metadata.get("phone_number_id") or ""
                    ).strip()
                    if metadata.get("display_phone_number") is not None:
                        business_phone = str(metadata["display_phone_number"])

                item = (
                    self._source_for_phone_number_id(phone_number_id)
                    if phone_number_id
                    else None
                )
                if item is None and entry_waba_id:
                    item = self._source_for_business_account_id(entry_waba_id)

                if field == "messages":
                    if item is None:
                        ignored += 1
                        continue
                    contact_names: dict[str, str] = {}
                    contacts = value.get("contacts")
                    if isinstance(contacts, list):
                        for contact in contacts:
                            if not isinstance(contact, dict):
                                continue
                            wa_id = "".join(
                                char
                                for char in str(contact.get("wa_id") or "")
                                if char.isdigit()
                            )
                            profile = contact.get("profile")
                            if (
                                wa_id
                                and isinstance(profile, dict)
                                and profile.get("name")
                            ):
                                contact_names[wa_id] = str(
                                    profile["name"]
                                ).strip()

                    incoming_messages = value.get("messages")
                    if isinstance(incoming_messages, list):
                        for message in incoming_messages:
                            if not isinstance(message, dict):
                                ignored += 1
                                continue
                            messages_count += 1
                            action, stored = self._handle_inbound_message(
                                item=item,
                                message=message,
                                contact_names=contact_names,
                                business_phone=business_phone,
                            )
                            if stored is None:
                                ignored += 1
                            elif action == "created":
                                created += 1
                            else:
                                updated += 1

                    statuses = value.get("statuses")
                    if isinstance(statuses, list):
                        for status_payload in statuses:
                            if not isinstance(status_payload, dict):
                                ignored += 1
                                continue
                            statuses_count += 1
                            if not self._handle_status(
                                status_payload=status_payload
                            ):
                                ignored += 1
                    continue

                if field == "smb_message_echoes":
                    if item is None:
                        ignored += 1
                        continue
                    echoes = value.get("message_echoes")
                    if not isinstance(echoes, list):
                        ignored += 1
                        continue
                    for message in echoes:
                        if not isinstance(message, dict):
                            ignored += 1
                            continue
                        echoes_count += 1
                        action, stored = self._handle_message_echo(
                            item=item,
                            message=message,
                            business_phone=business_phone,
                        )
                        if stored is None:
                            ignored += 1
                        elif action == "created":
                            created += 1
                        else:
                            updated += 1
                    continue

                if field == "history":
                    history = value.get("history")
                    history_events += (
                        len(history) if isinstance(history, list) else 1
                    )
                    if item is not None:
                        self.audit.record(
                            workspace_id=item.workspace_id,
                            entity_type="integration_source",
                            entity_public_id=item.public_id,
                            action="whatsapp_coexistence.history_webhook_received",
                            actor_type="integration",
                            after_data={
                                "events": (
                                    len(history)
                                    if isinstance(history, list)
                                    else 1
                                )
                            },
                        )
                        self.db.commit()
                    continue

                if field == "smb_app_state_sync":
                    state_sync = value.get("state_sync")
                    contact_sync_events += (
                        len(state_sync)
                        if isinstance(state_sync, list)
                        else 1
                    )
                    if item is not None:
                        self.audit.record(
                            workspace_id=item.workspace_id,
                            entity_type="integration_source",
                            entity_public_id=item.public_id,
                            action="whatsapp_coexistence.contact_sync_webhook_received",
                            actor_type="integration",
                            after_data={
                                "events": (
                                    len(state_sync)
                                    if isinstance(state_sync, list)
                                    else 1
                                )
                            },
                        )
                        self.db.commit()
                    continue

                ignored += 1

        return WhatsAppWebhookResult(
            messages=messages_count,
            statuses=statuses_count,
            created=created,
            updated=updated,
            ignored=ignored,
            echoes=echoes_count,
            history_events=history_events,
            contact_sync_events=contact_sync_events,
        )

    @staticmethod
    def _contains_template_placeholder(value: object) -> bool:
        if isinstance(value, str):
            return bool(_TEMPLATE_PARAMETER_RE.search(value))
        if isinstance(value, list):
            return any(
                WhatsAppCloudService._contains_template_placeholder(item)
                for item in value
            )
        if isinstance(value, dict):
            return any(
                WhatsAppCloudService._contains_template_placeholder(item)
                for item in value.values()
            )
        return False

    @classmethod
    def _template_descriptor(
        cls,
        template: WhatsAppTemplateInfo,
    ) -> dict[str, object]:
        body_text: str | None = None
        parameter_indexes: set[int] = set()
        unsupported_reason: str | None = None

        for component in template.components:
            component_type = str(component.get("type") or "").upper()
            if component_type == "BODY":
                text = component.get("text")
                if text is not None:
                    body_text = str(text)
                    parameter_indexes.update(
                        int(match.group(1))
                        for match in _TEMPLATE_PARAMETER_RE.finditer(body_text)
                    )
                continue

            if component_type == "HEADER":
                header_format = str(component.get("format") or "TEXT").upper()
                if header_format in {"IMAGE", "VIDEO", "DOCUMENT", "LOCATION"}:
                    unsupported_reason = (
                        "Template com cabeçalho de mídia ainda não é enviado por esta etapa."
                    )
                    break

            if cls._contains_template_placeholder(component):
                unsupported_reason = (
                    "Template possui variável fora do corpo da mensagem e exige um "
                    "componente que ainda não é suportado pelo envio controlado."
                )
                break

        parameter_count = max(parameter_indexes) if parameter_indexes else 0
        if parameter_indexes and parameter_indexes != set(
            range(1, parameter_count + 1)
        ):
            unsupported_reason = (
                "Template possui numeração de variáveis não sequencial no corpo."
            )
        if parameter_count > 20:
            unsupported_reason = (
                "Template excede o limite de 20 variáveis suportado pelo envio controlado."
            )

        return {
            "name": template.name,
            "language": template.language,
            "status": template.status,
            "category": template.category,
            "body_text": body_text,
            "parameter_count": parameter_count,
            "supported": unsupported_reason is None,
            "unsupported_reason": unsupported_reason,
        }

    def _template_context(
        self,
        item: IntegrationSource,
        *,
        limit: int = 100,
    ) -> tuple[WhatsAppGraphClient, str, list[WhatsAppTemplateInfo]]:
        config = dict(item.provider_config or {})
        business_account_id = str(
            config.get("business_account_id") or ""
        ).strip()
        if not business_account_id:
            raise WhatsAppNotConfiguredError(
                "WhatsApp Business Account ID não configurado."
            )
        token = self._secret_payload(item)["access_token"]
        client = WhatsAppGraphClient(access_token=token)
        templates = client.list_message_templates(
            business_account_id,
            limit=limit,
        )
        return client, business_account_id, templates

    def list_templates(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        item = self._source(workspace_public_id, integration_public_id)
        _, _, templates = self._template_context(item, limit=limit)
        approved = [
            self._template_descriptor(template)
            for template in templates
            if template.status.upper() == "APPROVED"
        ]
        return sorted(
            approved,
            key=lambda item: (str(item["name"]), str(item["language"])),
        )

    def _prepare_template(
        self,
        item: IntegrationSource,
        *,
        template_name: str,
        language_code: str,
        parameters: list[str],
    ) -> tuple[str, str]:
        _, _, templates = self._template_context(item)
        selected = next(
            (
                template
                for template in templates
                if template.status.upper() == "APPROVED"
                and template.name == template_name
                and template.language == language_code
            ),
            None,
        )
        if selected is None:
            raise WhatsAppIntegrationError(
                "Template aprovado não encontrado para o nome e idioma informados."
            )
        descriptor = self._template_descriptor(selected)
        if not bool(descriptor["supported"]):
            raise WhatsAppIntegrationError(
                str(descriptor["unsupported_reason"] or "Template não suportado.")
            )
        expected = int(descriptor["parameter_count"] or 0)
        if len(parameters) != expected:
            raise WhatsAppIntegrationError(
                f"Este template exige {expected} parâmetro(s) no corpo; "
                f"foram informados {len(parameters)}."
            )
        rendered = str(
            descriptor["body_text"] or f"[Template {template_name}]"
        )
        for index, value in enumerate(parameters, start=1):
            rendered = re.sub(
                rf"{{{{\s*{index}\s*}}}}",
                lambda _match, replacement=value: replacement,
                rendered,
            )
        canonical = json.dumps(
            {
                "kind": "whatsapp_template",
                "template_name": template_name,
                "language_code": language_code,
                "parameters": parameters,
                "rendered_text": rendered,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return rendered, canonical

    def preview_template(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        to: str,
        template_name: str,
        language_code: str,
        parameters: list[str],
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        CommunicationConsentService(self.db).assert_phone_allowed(
            workspace_id=item.workspace_id,
            phone=to,
            channel="whatsapp",
        )
        config = dict(item.provider_config or {})
        if not str(config.get("phone_number_id") or "").strip():
            raise WhatsAppNotConfiguredError(
                "Phone Number ID do WhatsApp não configurado."
            )
        rendered, canonical = self._prepare_template(
            item,
            template_name=template_name,
            language_code=language_code,
            parameters=parameters,
        )
        token, expires_at = create_whatsapp_confirmation(
            integration_public_id=item.public_id,
            to=to,
            text=canonical,
            ttl_seconds=300,
        )
        return {
            "to": to,
            "template_name": template_name,
            "language_code": language_code,
            "parameters": parameters,
            "rendered_text": rendered,
            "confirmation_token": token,
            "expires_at": expires_at,
        }

    def send_template(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        to: str,
        template_name: str,
        language_code: str,
        parameters: list[str],
        confirmation_token: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        rendered, canonical = self._prepare_template(
            item,
            template_name=template_name,
            language_code=language_code,
            parameters=parameters,
        )
        verify_whatsapp_confirmation(
            confirmation_token,
            integration_public_id=item.public_id,
            to=to,
            text=canonical,
        )
        return self._send_template_prepared(
            item,
            to=to,
            template_name=template_name,
            language_code=language_code,
            parameters=parameters,
            rendered=rendered,
        )

    def _send_template_prepared(
        self,
        item: IntegrationSource,
        *,
        to: str,
        template_name: str,
        language_code: str,
        parameters: list[str],
        rendered: str,
    ) -> dict[str, object]:
        CommunicationConsentService(self.db).assert_phone_allowed(
            workspace_id=item.workspace_id,
            phone=to,
            channel="whatsapp",
        )
        config = dict(item.provider_config or {})
        phone_number_id = str(config.get("phone_number_id") or "").strip()
        if not phone_number_id:
            raise WhatsAppNotConfiguredError(
                "Phone Number ID do WhatsApp não configurado."
            )
        token = self._secret_payload(item)["access_token"]
        provider_message_id = WhatsAppGraphClient(
            access_token=token
        ).send_template(
            phone_number_id=phone_number_id,
            to=to,
            template_name=template_name,
            language_code=language_code,
            body_parameters=parameters,
        )

        normalized_to = "".join(char for char in to if char.isdigit())
        lead = self.leads.find_duplicate(
            workspace_id=item.workspace_id,
            normalized_phone=normalized_to,
            normalized_email=None,
            external_id=None,
        )
        stored = self.messages.create(
            workspace_id=item.workspace_id,
            integration_source_id=item.id,
            lead_id=lead.id if lead is not None else None,
            provider_message_id=provider_message_id,
            direction="outbound",
            message_type="template",
            from_phone=str(config.get("display_phone_number") or "") or None,
            to_phone=to,
            body=rendered,
            status="sent",
            provider_timestamp=datetime.now(timezone.utc),
            metadata_json={
                "template_name": template_name,
                "language_code": language_code,
                "parameters": parameters,
            },
        )
        self._record_completed_activity(
            item=item,
            lead_id=lead.id if lead is not None else None,
            lead_public_id=lead.public_id if lead is not None else None,
            direction="outbound",
            body=rendered,
            actor_type="user",
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="whatsapp_message",
            entity_public_id=stored.public_id,
            action="whatsapp.template_sent",
            after_data={
                "provider_message_id": provider_message_id,
                "to": to,
                "template_name": template_name,
                "language_code": language_code,
                "lead_public_id": lead.public_id if lead is not None else None,
            },
        )
        self.db.commit()
        self.db.refresh(stored)
        return {
            "ok": True,
            "message_public_id": stored.public_id,
            "provider_message_id": provider_message_id,
            "to": to,
            "status": stored.status,
            "lead_public_id": lead.public_id if lead is not None else None,
        }

    def preview_message(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        to: str,
        text: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        CommunicationConsentService(self.db).assert_phone_allowed(
            workspace_id=item.workspace_id,
            phone=to,
            channel="whatsapp",
        )
        self._secret_payload(item)
        config = dict(item.provider_config or {})
        if not str(config.get("phone_number_id") or "").strip():
            raise WhatsAppNotConfiguredError(
                "Phone Number ID do WhatsApp não configurado."
            )
        token, expires_at = create_whatsapp_confirmation(
            integration_public_id=item.public_id,
            to=to,
            text=text,
            ttl_seconds=300,
        )
        return {
            "to": to,
            "text": text,
            "confirmation_token": token,
            "expires_at": expires_at,
        }

    def send_message(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        to: str,
        text: str,
        confirmation_token: str,
    ) -> dict[str, object]:
        item = self._source(workspace_public_id, integration_public_id)
        CommunicationConsentService(self.db).assert_phone_allowed(
            workspace_id=item.workspace_id,
            phone=to,
            channel="whatsapp",
        )
        verify_whatsapp_confirmation(
            confirmation_token,
            integration_public_id=item.public_id,
            to=to,
            text=text,
        )
        config = dict(item.provider_config or {})
        phone_number_id = str(config.get("phone_number_id") or "").strip()
        if not phone_number_id:
            raise WhatsAppNotConfiguredError(
                "Phone Number ID do WhatsApp não configurado."
            )
        token = self._secret_payload(item)["access_token"]
        provider_message_id = WhatsAppGraphClient(
            access_token=token
        ).send_text(
            phone_number_id=phone_number_id,
            to=to,
            text=text,
        )

        normalized_to = "".join(char for char in to if char.isdigit())
        lead = self.leads.find_duplicate(
            workspace_id=item.workspace_id,
            normalized_phone=normalized_to,
            normalized_email=None,
            external_id=None,
        )
        stored = self.messages.create(
            workspace_id=item.workspace_id,
            integration_source_id=item.id,
            lead_id=lead.id if lead is not None else None,
            provider_message_id=provider_message_id,
            direction="outbound",
            message_type="text",
            from_phone=str(config.get("display_phone_number") or "") or None,
            to_phone=to,
            body=text,
            status="sent",
            provider_timestamp=datetime.now(timezone.utc),
            metadata_json={},
        )
        self._record_completed_activity(
            item=item,
            lead_id=lead.id if lead is not None else None,
            lead_public_id=lead.public_id if lead is not None else None,
            direction="outbound",
            body=text,
            actor_type="user",
        )
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="whatsapp_message",
            entity_public_id=stored.public_id,
            action="whatsapp.message_sent",
            after_data={
                "provider_message_id": provider_message_id,
                "to": to,
                "lead_public_id": lead.public_id if lead is not None else None,
            },
        )
        self.db.commit()
        self.db.refresh(stored)
        return {
            "ok": True,
            "message_public_id": stored.public_id,
            "provider_message_id": provider_message_id,
            "to": to,
            "status": stored.status,
            "lead_public_id": lead.public_id if lead is not None else None,
        }

    def recent_messages(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        limit: int = 20,
    ) -> list[WhatsAppMessage]:
        item = self._source(workspace_public_id, integration_public_id)
        return self.messages.recent_for_source(
            integration_source_id=item.id,
            limit=limit,
        )
