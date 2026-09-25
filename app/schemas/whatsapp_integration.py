from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WhatsAppConfigure(BaseModel):
    phone_number_id: str = Field(min_length=3, max_length=80)
    access_token: str = Field(min_length=16, max_length=4096)
    business_account_id: str | None = Field(default=None, max_length=80)
    default_interest: str | None = Field(default="WhatsApp", max_length=255)

    @field_validator("phone_number_id", "access_token")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("business_account_id", "default_interest")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class WhatsAppStatusRead(BaseModel):
    integration_public_id: str
    configured: bool
    server_ready: bool
    subscribed: bool
    phone_number_id: str | None
    business_account_id: str | None
    display_phone_number: str | None
    verified_name: str | None
    default_interest: str | None
    graph_api_version: str
    webhook_endpoint: str
    token_hint: str | None
    recent_messages: int
    onboarding_mode: str | None = None
    coexistence: bool = False
    embedded_signup_connected: bool = False


class WhatsAppConnectionTestRead(BaseModel):
    ok: bool
    phone_number_id: str
    display_phone_number: str | None
    verified_name: str | None
    quality_rating: str | None
    graph_api_version: str


class WhatsAppSubscriptionRead(BaseModel):
    ok: bool
    business_account_id: str
    subscribed: bool = True


class WhatsAppMessagePreview(BaseModel):
    to: str = Field(min_length=8, max_length=30)
    text: str = Field(min_length=1, max_length=4096)

    @field_validator("to")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) < 8 or len(digits) > 20:
            raise ValueError("Número de WhatsApp inválido.")
        return digits

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Mensagem vazia.")
        return normalized


class WhatsAppMessagePreviewRead(BaseModel):
    to: str
    text: str
    confirmation_token: str
    expires_at: datetime


class WhatsAppMessageSend(WhatsAppMessagePreview):
    confirmation_token: str = Field(min_length=32, max_length=4096)


class WhatsAppMessageSendRead(BaseModel):
    ok: bool
    message_public_id: str
    provider_message_id: str
    to: str
    status: str
    lead_public_id: str | None


class WhatsAppTemplateRead(BaseModel):
    name: str
    language: str
    status: str
    category: str | None
    body_text: str | None
    parameter_count: int = 0
    supported: bool = True
    unsupported_reason: str | None = None


class WhatsAppTemplatePreviewRequest(BaseModel):
    to: str = Field(min_length=8, max_length=30)
    template_name: str = Field(min_length=1, max_length=512)
    language_code: str = Field(min_length=2, max_length=32)
    parameters: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("to")
    @classmethod
    def normalize_template_phone(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) < 8 or len(digits) > 20:
            raise ValueError("Número de WhatsApp inválido.")
        return digits

    @field_validator("template_name", "language_code")
    @classmethod
    def normalize_template_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Campo obrigatório não informado.")
        return normalized

    @field_validator("parameters")
    @classmethod
    def normalize_template_parameters(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = str(value).strip()
            if not item:
                raise ValueError("Parâmetros do template não podem ficar vazios.")
            if len(item) > 1024:
                raise ValueError("Parâmetro do template excede 1024 caracteres.")
            normalized.append(item)
        return normalized


class WhatsAppTemplatePreviewRead(BaseModel):
    to: str
    template_name: str
    language_code: str
    parameters: list[str]
    rendered_text: str
    confirmation_token: str
    expires_at: datetime


class WhatsAppTemplateSend(WhatsAppTemplatePreviewRequest):
    confirmation_token: str = Field(min_length=32, max_length=4096)


class WhatsAppMessageRead(BaseModel):
    public_id: str
    provider_message_id: str
    direction: str
    message_type: str
    from_phone: str | None
    to_phone: str | None
    body: str | None
    status: str
    error_code: str | None
    error_message: str | None
    provider_timestamp: datetime | None
    created_at: datetime
    updated_at: datetime


class WhatsAppWebhookRead(BaseModel):
    accepted: bool = True
    messages: int = 0
    statuses: int = 0
    created: int = 0
    updated: int = 0
    ignored: int = 0
    echoes: int = 0
    history_events: int = 0
    contact_sync_events: int = 0


class WhatsAppEmbeddedSignupConfigRead(BaseModel):
    enabled: bool
    app_id: str | None
    config_id: str | None
    graph_api_version: str
    feature_type: str = "whatsapp_business_app_onboarding"
    required_webhook_fields: list[str] = Field(default_factory=list)


class WhatsAppEmbeddedSignupComplete(BaseModel):
    code: str = Field(min_length=6, max_length=4096)
    waba_id: str | None = Field(default=None, max_length=80)
    phone_number_id: str | None = Field(default=None, max_length=80)
    event: str | None = Field(default=None, max_length=120)
    default_interest: str | None = Field(default="WhatsApp", max_length=255)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip()

    @field_validator("waba_id", "phone_number_id", "event", "default_interest")
    @classmethod
    def normalize_embedded_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class WhatsAppPhoneCandidateRead(BaseModel):
    phone_number_id: str
    display_phone_number: str | None
    verified_name: str | None
    quality_rating: str | None


class WhatsAppEmbeddedSignupCompleteRead(BaseModel):
    ok: bool
    connected: bool
    selection_required: bool = False
    business_account_id: str
    phone_number_id: str | None = None
    display_phone_number: str | None = None
    verified_name: str | None = None
    subscribed: bool = False
    coexistence: bool = True
    candidates: list[WhatsAppPhoneCandidateRead] = Field(default_factory=list)


class WhatsAppEmbeddedSignupSelectPhone(BaseModel):
    phone_number_id: str = Field(min_length=3, max_length=80)
    default_interest: str | None = Field(default="WhatsApp", max_length=255)

    @field_validator("phone_number_id")
    @classmethod
    def normalize_phone_number_id(cls, value: str) -> str:
        return value.strip()


class WhatsAppCoexistenceSyncRequest(BaseModel):
    sync_type: str

    @field_validator("sync_type")
    @classmethod
    def validate_sync_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"history", "smb_app_state_sync"}:
            raise ValueError(
                "sync_type inválido. Use history ou smb_app_state_sync."
            )
        return normalized


class WhatsAppCoexistenceSyncRead(BaseModel):
    ok: bool
    sync_type: str
    request_id: str | None = None
