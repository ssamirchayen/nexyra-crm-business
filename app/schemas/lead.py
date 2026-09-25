from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

VALID_PRIORITIES = frozenset(
    {
        "baixa",
        "media",
        "alta",
        "urgente",
    }
)


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    external_id: str | None = Field(default=None, max_length=160)

    interest: str | None = Field(default=None, max_length=255)
    source: str = Field(default="internet", min_length=2, max_length=80)
    channel: str = Field(default="web", min_length=2, max_length=80)
    campaign: str | None = Field(default=None, max_length=160)
    message: str | None = None

    status: str | None = Field(default=None, max_length=80)
    priority: str = Field(default="media", max_length=20)
    custom_fields: dict[str, object] = Field(default_factory=dict)

    owner_user_public_id: str | None = None
    consent: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if "@" not in normalized:
            raise ValueError("E-mail inválido.")
        return normalized

    @field_validator(
        "source",
        "channel",
        "priority",
        "status",
    )
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower().replace(" ", "_")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in VALID_PRIORITIES:
            raise ValueError(
                "Prioridade inválida. Use baixa, media, alta ou urgente."
            )
        return value


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    external_id: str | None = Field(default=None, max_length=160)

    interest: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, min_length=2, max_length=80)
    channel: str | None = Field(default=None, min_length=2, max_length=80)
    campaign: str | None = Field(default=None, max_length=160)
    message: str | None = None

    status: str | None = Field(default=None, max_length=80)
    priority: str | None = Field(default=None, max_length=20)
    custom_fields: dict[str, object] | None = None

    owner_user_public_id: str | None = None
    consent: bool | None = None
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if "@" not in normalized:
            raise ValueError("E-mail inválido.")
        return normalized

    @field_validator(
        "source",
        "channel",
        "priority",
        "status",
    )
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower().replace(" ", "_")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in VALID_PRIORITIES:
            raise ValueError(
                "Prioridade inválida. Use baixa, media, alta ou urgente."
            )
        return value


class LeadRead(BaseModel):
    public_id: str
    name: str
    phone: str | None
    email: str | None
    external_id: str | None

    interest: str | None
    source: str
    channel: str
    campaign: str | None
    message: str | None

    status: str
    priority: str
    custom_fields: dict[str, object]

    owner_user_public_id: str | None
    consent: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class LeadIntakeRead(BaseModel):
    action: str
    lead: LeadRead


class LeadPageRead(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    page_size: int
    total_pages: int
