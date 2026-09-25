from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

VALID_OPPORTUNITY_STATUSES = frozenset(
    {
        "open",
        "won",
        "lost",
    }
)


class OpportunityCreate(BaseModel):
    lead_public_id: str
    title: str | None = Field(default=None, max_length=200)
    value_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    stage: str | None = Field(default=None, max_length=80)
    owner_user_public_id: str | None = None
    expected_close_date: date | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("stage")
    @classmethod
    def normalize_stage(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower().replace(" ", "_")


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    value_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    owner_user_public_id: str | None = None
    expected_close_date: date | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class OpportunityMove(BaseModel):
    to_stage: str = Field(min_length=2, max_length=80)
    changed_by_user_public_id: str | None = None
    note: str | None = None

    @field_validator("to_stage")
    @classmethod
    def normalize_stage(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")


class OpportunityWon(BaseModel):
    changed_by_user_public_id: str | None = None
    note: str | None = None


class OpportunityLost(BaseModel):
    reason: str = Field(min_length=2)
    changed_by_user_public_id: str | None = None
    note: str | None = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return " ".join(value.strip().split())


class OpportunityRead(BaseModel):
    public_id: str
    lead_public_id: str
    owner_user_public_id: str | None

    title: str
    value_amount: Decimal
    currency: str

    stage: str
    status: str
    expected_close_date: date | None
    loss_reason: str | None

    won_at: datetime | None
    lost_at: datetime | None


class OpportunityCardRead(BaseModel):
    public_id: str
    lead_public_id: str
    lead_name: str
    lead_phone: str | None
    lead_email: str | None
    lead_interest: str | None
    owner_user_public_id: str | None
    owner_name: str | None

    title: str
    value_amount: Decimal
    currency: str
    stage: str
    status: str
    expected_close_date: date | None
    loss_reason: str | None
    won_at: datetime | None
    lost_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OpportunityPageRead(BaseModel):
    items: list[OpportunityCardRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class PipelineStageRead(BaseModel):
    code: str
    total_count: int
    total_value: Decimal
    opportunities: list[OpportunityCardRead]


class PipelineBoardRead(BaseModel):
    workspace_public_id: str
    pipeline: list[str]
    open_opportunities: int
    total_pipeline_value: Decimal
    stages: list[PipelineStageRead]


class OpportunityStageHistoryRead(BaseModel):
    from_stage: str | None
    to_stage: str
    changed_by_user_public_id: str | None
    note: str | None
    created_at: datetime


class OpportunityMetricsRead(BaseModel):
    total_opportunities: int
    open_opportunities: int
    won_opportunities: int
    lost_opportunities: int
    conversion_rate: float
    total_pipeline_value: Decimal
    won_value: Decimal
    average_won_value: Decimal
