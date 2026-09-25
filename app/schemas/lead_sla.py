from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SlaState = Literal["within_sla", "warning", "breached", "contacted"]


class LeadSlaConfigUpdate(BaseModel):
    enabled: bool = True
    first_response_minutes: int = Field(default=15, ge=1, le=1440)
    warning_before_minutes: int = Field(default=5, ge=0, le=1439)
    follow_up_due_hours: int = Field(default=24, ge=1, le=168)
    stale_lead_hours: int = Field(default=24, ge=1, le=720)

    @model_validator(mode="after")
    def validate_warning_window(self) -> LeadSlaConfigUpdate:
        if self.warning_before_minutes >= self.first_response_minutes:
            raise ValueError(
                "O alerta antecipado deve ser menor que o SLA de primeiro contato."
            )
        return self


class LeadSlaConfigRead(LeadSlaConfigUpdate):
    pass


class LeadSlaQueueItemRead(BaseModel):
    lead_public_id: str
    lead_name: str
    phone: str | None
    interest: str | None
    status: str
    priority: str
    source: str
    owner_user_public_id: str | None
    owner_name: str | None
    created_at: datetime
    age_minutes: int
    first_contact_at: datetime | None
    first_response_minutes: int | None
    sla_due_at: datetime
    sla_state: SlaState
    last_contact_at: datetime | None
    pending_followups: int
    overdue_followups: int
    next_followup_due_at: datetime | None
    stale: bool
    score: int
    reasons: list[str]


class LeadSlaQueueMetricsRead(BaseModel):
    total_attention: int
    awaiting_first_contact: int
    sla_warning: int
    sla_breached: int
    overdue_followups: int
    due_soon_followups: int
    stale_leads: int
    unassigned: int


class LeadSlaQueueRead(BaseModel):
    config: LeadSlaConfigRead
    metrics: LeadSlaQueueMetricsRead
    items: list[LeadSlaQueueItemRead]
