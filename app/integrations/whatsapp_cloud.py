from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class WhatsAppGraphError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WhatsAppPhoneInfo:
    phone_number_id: str
    display_phone_number: str | None
    verified_name: str | None
    quality_rating: str | None


@dataclass(frozen=True, slots=True)
class WhatsAppTemplateInfo:
    name: str
    language: str
    status: str
    category: str | None
    components: list[dict[str, Any]]


class WhatsAppGraphClient:
    def __init__(
        self,
        *,
        access_token: str,
        api_version: str | None = None,
    ) -> None:
        settings = get_settings()
        self.access_token = access_token
        self.api_version = (
            api_version or settings.whatsapp_graph_api_version
        ).strip()
        self.base_url = settings.whatsapp_graph_base_url.rstrip("/")
        self.timeout = settings.whatsapp_http_timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _graph_error_message(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        error = payload.get("error")
        if not isinstance(error, dict):
            return None
        message = error.get("message")
        if message is None:
            return None
        return str(message)

    @classmethod
    def exchange_embedded_signup_code(
        cls,
        *,
        code: str,
        app_id: str,
        app_secret: str,
        api_version: str | None = None,
    ) -> str:
        settings = get_settings()
        version = (api_version or settings.whatsapp_graph_api_version).strip()
        url = f"{settings.whatsapp_graph_base_url.rstrip('/')}/{version}/oauth/access_token"
        try:
            response = httpx.get(
                url,
                params={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "code": code,
                },
                timeout=settings.whatsapp_http_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            detail = cls._graph_error_message(exc.response)
            suffix = f" Detalhe Meta: {detail}" if detail else ""
            raise WhatsAppGraphError(
                "A Meta recusou a troca do código do Embedded Signup."
                + suffix
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "Não foi possível trocar o código do Embedded Signup com a Meta."
            ) from exc
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise WhatsAppGraphError(
                "A Meta não retornou um Access Token após o Embedded Signup."
            )
        return str(payload["access_token"])

    @classmethod
    def discover_waba_ids(
        cls,
        *,
        user_access_token: str,
        app_id: str,
        app_secret: str,
        api_version: str | None = None,
    ) -> list[str]:
        settings = get_settings()
        version = (api_version or settings.whatsapp_graph_api_version).strip()
        url = f"{settings.whatsapp_graph_base_url.rstrip('/')}/{version}/debug_token"
        app_access_token = f"{app_id}|{app_secret}"
        try:
            response = httpx.get(
                url,
                params={
                    "input_token": user_access_token,
                    "access_token": app_access_token,
                },
                timeout=settings.whatsapp_http_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "Não foi possível descobrir a conta WhatsApp compartilhada pelo Embedded Signup."
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        granular_scopes = (
            data.get("granular_scopes") if isinstance(data, dict) else None
        )
        result: list[str] = []
        if isinstance(granular_scopes, list):
            for scope in granular_scopes:
                if not isinstance(scope, dict):
                    continue
                if scope.get("scope") != "whatsapp_business_management":
                    continue
                targets = scope.get("target_ids")
                if not isinstance(targets, list):
                    continue
                for target in targets:
                    value = str(target).strip()
                    if value and value not in result:
                        result.append(value)
        return result

    @staticmethod
    def _phone_info(payload: dict[str, Any], fallback_id: str) -> WhatsAppPhoneInfo:
        return WhatsAppPhoneInfo(
            phone_number_id=str(payload.get("id") or fallback_id),
            display_phone_number=(
                str(payload.get("display_phone_number"))
                if payload.get("display_phone_number") is not None
                else None
            ),
            verified_name=(
                str(payload.get("verified_name"))
                if payload.get("verified_name") is not None
                else None
            ),
            quality_rating=(
                str(payload.get("quality_rating"))
                if payload.get("quality_rating") is not None
                else None
            ),
        )

    def test_phone_number(self, phone_number_id: str) -> WhatsAppPhoneInfo:
        url = f"{self.base_url}/{self.api_version}/{phone_number_id}"
        try:
            response = httpx.get(
                url,
                params={
                    "fields": (
                        "id,display_phone_number,verified_name,quality_rating"
                    )
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "A WhatsApp Cloud API recusou a solicitação ou não respondeu corretamente."
            ) from exc
        if not isinstance(payload, dict):
            raise WhatsAppGraphError("Resposta inválida da WhatsApp Cloud API.")
        return self._phone_info(payload, phone_number_id)

    def list_phone_numbers(self, business_account_id: str) -> list[WhatsAppPhoneInfo]:
        url = (
            f"{self.base_url}/{self.api_version}/"
            f"{business_account_id}/phone_numbers"
        )
        try:
            response = httpx.get(
                url,
                params={
                    "fields": (
                        "id,display_phone_number,verified_name,quality_rating"
                    )
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "Não foi possível listar os números do WhatsApp Business compartilhado."
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise WhatsAppGraphError(
                "A Meta retornou uma lista de números inválida."
            )
        result: list[WhatsAppPhoneInfo] = []
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            result.append(self._phone_info(item, str(item["id"])))
        return result

    def subscribe_business_account(self, business_account_id: str) -> None:
        url = (
            f"{self.base_url}/{self.api_version}/"
            f"{business_account_id}/subscribed_apps"
        )
        try:
            response = httpx.post(
                url,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "Não foi possível assinar a conta do WhatsApp Business para webhooks."
            ) from exc
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise WhatsAppGraphError(
                "A Meta não confirmou a assinatura da conta do WhatsApp Business."
            )

    def request_business_app_sync(
        self,
        *,
        phone_number_id: str,
        sync_type: str,
    ) -> str | None:
        url = (
            f"{self.base_url}/{self.api_version}/"
            f"{phone_number_id}/smb_app_data"
        )
        payload = {
            "messaging_product": "whatsapp",
            "sync_type": sync_type,
        }
        try:
            response = httpx.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "A Meta não aceitou a solicitação de sincronização do WhatsApp Business App."
            ) from exc
        if not isinstance(result, dict):
            raise WhatsAppGraphError(
                "Resposta inválida ao solicitar sincronização do WhatsApp Business App."
            )
        request_id = result.get("request_id")
        return str(request_id) if request_id is not None else None

    def list_message_templates(
        self,
        business_account_id: str,
        *,
        limit: int = 100,
    ) -> list[WhatsAppTemplateInfo]:
        url = (
            f"{self.base_url}/{self.api_version}/"
            f"{business_account_id}/message_templates"
        )
        try:
            response = httpx.get(
                url,
                params={
                    "fields": "name,language,status,category,components",
                    "limit": max(1, min(limit, 100)),
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "Não foi possível consultar os templates do WhatsApp Business."
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise WhatsAppGraphError(
                "A Meta retornou uma lista de templates inválida."
            )
        result: list[WhatsAppTemplateInfo] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            language = str(item.get("language") or "").strip()
            status = str(item.get("status") or "").strip().upper()
            if not name or not language or not status:
                continue
            raw_components = item.get("components")
            components = (
                [component for component in raw_components if isinstance(component, dict)]
                if isinstance(raw_components, list)
                else []
            )
            category = item.get("category")
            result.append(
                WhatsAppTemplateInfo(
                    name=name,
                    language=language,
                    status=status,
                    category=str(category) if category is not None else None,
                    components=components,
                )
            )
        return result

    def send_template(
        self,
        *,
        phone_number_id: str,
        to: str,
        template_name: str,
        language_code: str,
        body_parameters: list[str],
    ) -> str:
        url = (
            f"{self.base_url}/{self.api_version}/"
            f"{phone_number_id}/messages"
        )
        template: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if body_parameters:
            template["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": value}
                        for value in body_parameters
                    ],
                }
            ]
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template,
        }
        try:
            response = httpx.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "Não foi possível enviar o template pela WhatsApp Cloud API."
            ) from exc
        messages = result.get("messages") if isinstance(result, dict) else None
        if not isinstance(messages, list) or not messages:
            raise WhatsAppGraphError(
                "A WhatsApp Cloud API não retornou o identificador da mensagem."
            )
        first = messages[0]
        if not isinstance(first, dict) or not first.get("id"):
            raise WhatsAppGraphError(
                "A WhatsApp Cloud API não retornou o identificador da mensagem."
            )
        return str(first["id"])

    def send_text(self, *, phone_number_id: str, to: str, text: str) -> str:
        url = (
            f"{self.base_url}/{self.api_version}/"
            f"{phone_number_id}/messages"
        )
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            response = httpx.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppGraphError(
                "Não foi possível enviar a mensagem pela WhatsApp Cloud API."
            ) from exc
        messages = result.get("messages") if isinstance(result, dict) else None
        if not isinstance(messages, list) or not messages:
            raise WhatsAppGraphError(
                "A WhatsApp Cloud API não retornou o identificador da mensagem."
            )
        first = messages[0]
        if not isinstance(first, dict) or not first.get("id"):
            raise WhatsAppGraphError(
                "A WhatsApp Cloud API não retornou o identificador da mensagem."
            )
        return str(first["id"])
