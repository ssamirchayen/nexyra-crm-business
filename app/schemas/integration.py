from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CODE_PATTERN = re.compile(r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")

_SECRET_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "api_key",
    "access_key",
    "refresh_key",
)


def _inspect_config_value(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = str(key).strip().lower()
            if any(part in normalized_key for part in _SECRET_KEY_PARTS):
                raise ValueError(
                    "Credenciais secretas não podem ser salvas em provider_config."
                )
            _inspect_config_value(nested)
    elif isinstance(value, list):
        for nested in value:
            _inspect_config_value(nested)


def _reject_secret_config(value: dict[str, object]) -> dict[str, object]:
    _inspect_config_value(value)
    return value


def _normalize_code(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if not _CODE_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Use apenas letras minúsculas, números, hífen ou underline."
        )
    return normalized


class IntegrationProviderRead(BaseModel):
    code: str
    label: str
    description: str
    category: str
    availability: str
    default_source: str
    default_channel: str
    supports_multiple: bool
    capabilities: list[str]


class IntegrationSourceCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    source: str = Field(min_length=2, max_length=80)
    channel: str = Field(min_length=2, max_length=80)
    default_campaign: str | None = Field(default=None, max_length=160)
    routing_config: dict[str, object] = Field(default_factory=dict)
    provider_config: dict[str, object] = Field(default_factory=dict)
    active: bool = True

    @field_validator("provider", "source", "channel")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return _normalize_code(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("default_campaign")
    @classmethod
    def normalize_campaign(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("provider_config")
    @classmethod
    def reject_secret_config(cls, value: dict[str, object]) -> dict[str, object]:
        return _reject_secret_config(value)


class IntegrationSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    source: str | None = Field(default=None, min_length=2, max_length=80)
    channel: str | None = Field(default=None, min_length=2, max_length=80)
    default_campaign: str | None = Field(default=None, max_length=160)
    routing_config: dict[str, object] | None = None
    provider_config: dict[str, object] | None = None
    active: bool | None = None

    @field_validator("source", "channel")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_code(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())

    @field_validator("default_campaign")
    @classmethod
    def normalize_campaign(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("provider_config")
    @classmethod
    def reject_secret_config(
        cls,
        value: dict[str, object] | None,
    ) -> dict[str, object] | None:
        if value is None:
            return None
        return _reject_secret_config(value)


class IntegrationCredentialRead(BaseModel):
    integration_public_id: str
    intake_key: str
    key_prefix: str
    intake_endpoint: str
    header_name: str = "X-Nexyra-Intake-Key"


class ExternalLeadIntakeRead(BaseModel):
    action: str
    lead_public_id: str
    source: str
    channel: str
    campaign: str | None
    intake_count: int


class IntegrationSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    provider: str
    name: str
    source: str
    channel: str
    default_campaign: str | None
    routing_config: dict[str, object]
    provider_config: dict[str, object]
    active: bool
    external_intake_enabled: bool
    intake_key_prefix: str | None
    intake_count: int
    last_intake_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IntegrationOverviewRead(BaseModel):
    providers: list[IntegrationProviderRead]
    sources: list[IntegrationSourceRead]
    active_sources: int
    intake_endpoint: str
