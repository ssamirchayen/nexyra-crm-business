from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WhatsAppBulkPreviewRequest(BaseModel):
    lead_public_ids: list[str] = Field(min_length=1, max_length=25)
    integration_public_id: str = Field(min_length=1, max_length=64)
    template_name: str = Field(min_length=1, max_length=512)
    language_code: str = Field(min_length=2, max_length=32)
    parameter_templates: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("lead_public_ids")
    @classmethod
    def normalize_lead_ids(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in result:
                result.append(item)
        if not result:
            raise ValueError("Selecione ao menos um lead.")
        return result

    @field_validator("integration_public_id", "template_name", "language_code")
    @classmethod
    def normalize_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Campo obrigatório não informado.")
        return normalized

    @field_validator("parameter_templates")
    @classmethod
    def normalize_parameters(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = str(value).strip()
            if not item:
                raise ValueError("Parâmetros do template não podem ficar vazios.")
            if len(item) > 1024:
                raise ValueError("Parâmetro do template excede 1024 caracteres.")
            result.append(item)
        return result




class WhatsAppBulkSourceRead(BaseModel):
    public_id: str
    name: str

class WhatsAppBulkRecipientPreviewRead(BaseModel):
    lead_public_id: str
    lead_name: str
    phone: str | None
    eligible: bool
    reason: str
    parameters: list[str]
    rendered_text: str | None


class WhatsAppBulkPreviewRead(BaseModel):
    requested: int
    eligible: int
    blocked: int
    integration_public_id: str
    template_name: str
    language_code: str
    parameter_templates: list[str]
    confirmation_token: str
    expires_at: datetime
    recipients: list[WhatsAppBulkRecipientPreviewRead]


class WhatsAppBulkSendRequest(WhatsAppBulkPreviewRequest):
    confirmation_token: str = Field(min_length=32, max_length=4096)


class WhatsAppBulkSendItemRead(BaseModel):
    lead_public_id: str
    lead_name: str
    phone: str | None
    status: str
    provider_message_id: str | None = None
    error: str | None = None


class WhatsAppBulkSendRead(BaseModel):
    requested: int
    attempted: int
    sent: int
    failed: int
    blocked: int
    items: list[WhatsAppBulkSendItemRead]
