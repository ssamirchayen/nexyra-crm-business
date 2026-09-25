from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class MetaLeadAdsConfigure(BaseModel):
    page_id: str = Field(min_length=3, max_length=80)
    page_access_token: str = Field(min_length=16, max_length=4096)
    form_ids: list[str] = Field(default_factory=list, max_length=100)
    interest_field: str | None = Field(default=None, max_length=120)
    default_interest: str | None = Field(default="Meta Lead Ads", max_length=255)

    @field_validator("page_id", "page_access_token")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("form_ids")
    @classmethod
    def normalize_forms(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            normalized = item.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    @field_validator("interest_field", "default_interest")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class MetaLeadAdsStatusRead(BaseModel):
    integration_public_id: str
    configured: bool
    server_ready: bool
    subscribed: bool
    page_id: str | None
    form_ids: list[str]
    interest_field: str | None
    default_interest: str | None
    graph_api_version: str
    webhook_endpoint: str
    token_hint: str | None


class MetaLeadAdsSubscriptionRead(BaseModel):
    ok: bool
    page_id: str
    subscribed: bool = True


class MetaLeadAdsConnectionTestRead(BaseModel):
    ok: bool
    page_id: str
    page_name: str | None
    graph_api_version: str


class MetaWebhookRead(BaseModel):
    accepted: bool = True
    events: int = 0
    created: int = 0
    updated: int = 0
    ignored: int = 0
