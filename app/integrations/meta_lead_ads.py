from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class MetaGraphError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MetaLeadData:
    leadgen_id: str
    form_id: str | None
    campaign_name: str | None
    fields: dict[str, str]


class MetaGraphClient:
    def __init__(self, *, access_token: str, api_version: str | None = None) -> None:
        settings = get_settings()
        self.access_token = access_token
        self.api_version = (api_version or settings.meta_graph_api_version).strip()
        self.base_url = settings.meta_graph_base_url.rstrip("/")
        self.timeout = settings.meta_http_timeout_seconds

    def _get(self, object_id: str, fields: str) -> dict[str, Any]:
        url = f"{self.base_url}/{self.api_version}/{object_id}"
        try:
            response = httpx.get(
                url,
                params={"fields": fields},
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MetaGraphError(
                "A Meta Graph API recusou a solicitação ou não respondeu corretamente."
            ) from exc
        if not isinstance(payload, dict):
            raise MetaGraphError("Resposta inválida da Meta Graph API.")
        return payload

    def subscribe_page(self, page_id: str) -> None:
        url = f"{self.base_url}/{self.api_version}/{page_id}/subscribed_apps"
        try:
            response = httpx.post(
                url,
                data={"subscribed_fields": "leadgen"},
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MetaGraphError(
                "Não foi possível assinar a Página Meta para o evento leadgen."
            ) from exc
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise MetaGraphError(
                "A Meta não confirmou a assinatura do evento leadgen."
            )

    def test_page(self, page_id: str) -> tuple[str, str | None]:
        payload = self._get(page_id, "id,name")
        returned_id = str(payload.get("id") or page_id)
        name = payload.get("name")
        return returned_id, str(name) if name is not None else None

    def fetch_lead(self, leadgen_id: str) -> MetaLeadData:
        payload = self._get(
            leadgen_id,
            (
                "id,created_time,form_id,ad_id,ad_name,adset_id,adset_name,"
                "campaign_id,campaign_name,field_data"
            ),
        )
        field_data = payload.get("field_data")
        fields: dict[str, str] = {}
        if isinstance(field_data, list):
            for item in field_data:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                values = item.get("values")
                if not isinstance(name, str) or not isinstance(values, list) or not values:
                    continue
                first = values[0]
                if first is not None:
                    fields[name.strip().lower()] = str(first).strip()
        return MetaLeadData(
            leadgen_id=str(payload.get("id") or leadgen_id),
            form_id=str(payload.get("form_id")) if payload.get("form_id") else None,
            campaign_name=(
                str(payload.get("campaign_name"))
                if payload.get("campaign_name") is not None
                else None
            ),
            fields=fields,
        )
