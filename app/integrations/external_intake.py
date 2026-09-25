from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models import IntegrationSource
from app.schemas import LeadCreate


class ExternalIntakePayloadError(ValueError):
    pass


_STANDARD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "nome", "full_name", "fullname", "contact.name"),
    "phone": (
        "phone",
        "telefone",
        "celular",
        "mobile",
        "whatsapp",
        "contact.phone",
    ),
    "email": ("email", "e-mail", "mail", "contact.email"),
    "external_id": ("external_id", "lead_id", "contact_id", "id"),
    "interest": (
        "interest",
        "interesse",
        "curso",
        "produto",
        "service",
        "servico",
    ),
    "campaign": ("campaign", "campanha", "utm_campaign"),
    "message": ("message", "mensagem", "notes", "observacao", "observações"),
    "consent": ("consent", "lgpd_consent", "consentimento"),
}


def _read_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _first_value(payload: Mapping[str, Any], paths: tuple[str, ...]) -> Any:
    for path in paths:
        value = _read_path(payload, path)
        if value is not None and value != "":
            return value
    return None


def _normalize_bool(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "sim", "yes", "on"}:
            return True
        if normalized in {"0", "false", "nao", "não", "no", "off"}:
            return False
    return None


def build_external_lead_payload(
    source: IntegrationSource,
    payload: Mapping[str, Any],
    *,
    idempotency_key: str | None = None,
) -> LeadCreate:
    provider_config = dict(source.provider_config or {})
    configured_mapping = provider_config.get("field_mapping")
    field_mapping = (
        configured_mapping if isinstance(configured_mapping, dict) else {}
    )

    values: dict[str, Any] = {}
    for field_name, aliases in _STANDARD_ALIASES.items():
        configured_path = field_mapping.get(field_name)
        if isinstance(configured_path, str) and configured_path.strip():
            value = _read_path(payload, configured_path.strip())
        else:
            value = _first_value(payload, aliases)
        if value is not None and value != "":
            values[field_name] = value

    if "name" not in values:
        raise ExternalIntakePayloadError(
            "O payload externo precisa informar o nome do lead. "
            "Use 'name', 'nome' ou configure provider_config.field_mapping."
        )

    if idempotency_key and "external_id" not in values:
        values["external_id"] = idempotency_key[:160]

    payload_custom_fields = payload.get("custom_fields")
    custom_fields: dict[str, object] = {}
    if isinstance(payload_custom_fields, dict):
        custom_fields.update(payload_custom_fields)

    configured_custom_mapping = provider_config.get("custom_field_mapping")
    if isinstance(configured_custom_mapping, dict):
        for destination, path in configured_custom_mapping.items():
            if not isinstance(destination, str) or not isinstance(path, str):
                continue
            value = _read_path(payload, path)
            if value is not None:
                custom_fields[destination] = value

    if custom_fields:
        values["custom_fields"] = custom_fields

    routing = dict(source.routing_config or {})
    for field_name in ("owner_user_public_id", "priority", "status"):
        if field_name not in values and routing.get(field_name) is not None:
            values[field_name] = routing[field_name]

    consent = _normalize_bool(values.get("consent"))
    if consent is not None:
        values["consent"] = consent
    elif "consent" in values:
        values.pop("consent")

    values["source"] = source.source
    values["channel"] = source.channel
    if not values.get("campaign") and source.default_campaign:
        values["campaign"] = source.default_campaign

    return LeadCreate.model_validate(values)
