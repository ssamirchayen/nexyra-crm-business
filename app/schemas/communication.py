from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

COMMUNICATION_CHANNELS = frozenset({"whatsapp", "email", "sms", "phone"})
CONSENT_CHANNELS = frozenset({*COMMUNICATION_CHANNELS, "all"})
CONSENT_STATUSES = frozenset({"granted", "denied", "revoked", "unknown"})
LAWFUL_BASES = frozenset(
    {
        "consent",
        "contract",
        "legitimate_interest",
        "customer_request",
        "other",
    }
)


class CommunicationPolicyUpdate(BaseModel):
    enforce_whatsapp_opt_in: bool = True
    enforce_email_opt_in: bool = True
    enforce_sms_opt_in: bool = True
    enforce_phone_opt_in: bool = False
    allow_legacy_lead_consent: bool = True
    stop_cadence_on_block: bool = True


class CommunicationPolicyRead(CommunicationPolicyUpdate):
    updated_at: datetime | None = None


class LeadConsentUpsert(BaseModel):
    channel: str
    status: str
    lawful_basis: str | None = None
    source: str | None = Field(default=None, max_length=80)
    evidence: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in CONSENT_CHANNELS:
            raise ValueError("Canal de comunicação inválido.")
        return normalized

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in CONSENT_STATUSES:
            raise ValueError("Status de consentimento inválido.")
        return normalized

    @field_validator("lawful_basis")
    @classmethod
    def validate_lawful_basis(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in LAWFUL_BASES:
            raise ValueError("Base legal inválida.")
        return normalized


class LeadOptOutRequest(BaseModel):
    channel: str = "all"
    source: str | None = Field(default="manual", max_length=80)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in CONSENT_CHANNELS:
            raise ValueError("Canal de comunicação inválido.")
        return normalized


class LeadConsentRead(BaseModel):
    public_id: str | None
    channel: str
    status: str
    lawful_basis: str | None
    source: str | None
    evidence: str | None
    note: str | None
    granted_at: datetime | None
    revoked_at: datetime | None
    updated_at: datetime | None
    explicit: bool
    allowed: bool
    effective_reason: str


class LeadCommunicationSummaryRead(BaseModel):
    lead_public_id: str
    legacy_consent: bool
    global_opt_out: bool
    items: list[LeadConsentRead]


class CommunicationEligibilityRead(BaseModel):
    lead_public_id: str
    channel: str
    allowed: bool
    reason: str
