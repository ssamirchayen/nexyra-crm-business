from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

VALID_CADENCE_ACTIONS = frozenset({"call", "whatsapp", "email", "follow_up", "task"})


class LeadCadenceStepInput(BaseModel):
    delay_minutes: int = Field(ge=0, le=525600)
    action_type: str
    title: str = Field(min_length=2, max_length=200)
    message_template: str | None = Field(default=None, max_length=4000)

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_CADENCE_ACTIONS:
            raise ValueError("Ação da cadência inválida.")
        return normalized


class LeadCadenceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    active: bool = True
    stop_on_reply: bool = True
    steps: list[LeadCadenceStepInput] = Field(min_length=1, max_length=20)


class LeadCadenceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    active: bool | None = None
    stop_on_reply: bool | None = None
    steps: list[LeadCadenceStepInput] | None = Field(default=None, min_length=1, max_length=20)


class LeadCadenceStepRead(BaseModel):
    position: int
    delay_minutes: int
    action_type: str
    title: str
    message_template: str | None


class LeadCadenceRead(BaseModel):
    public_id: str
    name: str
    description: str | None
    active: bool
    stop_on_reply: bool
    steps: list[LeadCadenceStepRead]
    active_enrollments: int = 0
    created_at: datetime
    updated_at: datetime


class LeadCadenceEnrollRequest(BaseModel):
    lead_public_id: str
    cadence_public_id: str


class LeadCadenceEnrollmentRead(BaseModel):
    public_id: str
    lead_public_id: str
    lead_name: str
    cadence_public_id: str
    cadence_name: str
    status: str
    current_step: int
    total_steps: int
    next_run_at: datetime | None
    started_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None


class LeadCadenceProcessRead(BaseModel):
    processed: int
    activities_created: int
    completed: int
    cancelled: int


class LeadCadencePreviewItem(BaseModel):
    position: int
    scheduled_at: datetime
    action_type: str
    title: str


class LeadCadencePreviewRead(BaseModel):
    items: list[LeadCadencePreviewItem]
