from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.lead import VALID_PRIORITIES

DistributionStrategy = Literal["least_loaded", "round_robin"]


class LeadDistributionRule(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    enabled: bool = True
    source: str | None = Field(default=None, max_length=80)
    channel: str | None = Field(default=None, max_length=80)
    interest_contains: str | None = Field(default=None, max_length=160)
    campaign_contains: str | None = Field(default=None, max_length=160)
    priorities: list[str] = Field(default_factory=list, max_length=4)
    eligible_user_public_ids: list[str] = Field(default_factory=list, max_length=100)
    strategy: DistributionStrategy | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("source", "channel")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "_")
        return normalized or None

    @field_validator("interest_contains", "campaign_contains")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("priorities")
    @classmethod
    def normalize_priorities(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            item = value.strip().lower().replace(" ", "_")
            if item not in VALID_PRIORITIES:
                raise ValueError(
                    "Prioridade inválida em regra de distribuição."
                )
            if item not in normalized:
                normalized.append(item)
        return normalized

    @field_validator("eligible_user_public_ids")
    @classmethod
    def unique_users(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in result:
                result.append(item)
        return result

    @model_validator(mode="after")
    def require_condition(self) -> LeadDistributionRule:
        if not any(
            (
                self.source,
                self.channel,
                self.interest_contains,
                self.campaign_contains,
                self.priorities,
            )
        ):
            raise ValueError(
                "A regra precisa ter ao menos um critério de Lead."
            )
        return self


class LeadDistributionConfigUpdate(BaseModel):
    enabled: bool = False
    strategy: DistributionStrategy = "least_loaded"
    eligible_roles: list[str] = Field(default_factory=lambda: ["seller"], max_length=10)
    eligible_user_public_ids: list[str] = Field(default_factory=list, max_length=100)
    rules: list[LeadDistributionRule] = Field(default_factory=list, max_length=50)

    @field_validator("eligible_roles")
    @classmethod
    def normalize_roles(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = value.strip().lower()
            if item and item not in result:
                result.append(item)
        if not result:
            raise ValueError("Selecione ao menos um perfil elegível.")
        return result

    @field_validator("eligible_user_public_ids")
    @classmethod
    def unique_users(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in result:
                result.append(item)
        return result


class LeadDistributionConfigRead(BaseModel):
    enabled: bool
    strategy: DistributionStrategy
    eligible_roles: list[str]
    eligible_user_public_ids: list[str]
    rules: list[LeadDistributionRule]


class LeadDistributionMemberRead(BaseModel):
    user_public_id: str
    name: str
    role: str
    active: bool
    eligible: bool
    assigned_active_leads: int


class LeadDistributionSummaryRead(BaseModel):
    config: LeadDistributionConfigRead
    members: list[LeadDistributionMemberRead]
    unassigned_active_leads: int
    total_active_leads: int


class LeadDistributionRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    dry_run: bool = False


class LeadDistributionAssignmentRead(BaseModel):
    lead_public_id: str
    user_public_id: str
    user_name: str
    strategy: DistributionStrategy
    rule_name: str | None
    previous_load: int


class LeadDistributionRunRead(BaseModel):
    dry_run: bool
    scanned: int
    assigned: int
    skipped: int
    assignments: list[LeadDistributionAssignmentRead]
