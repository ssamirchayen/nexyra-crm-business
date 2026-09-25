from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

VALID_ACTIVITY_TYPES = frozenset(
    {"call", "whatsapp", "email", "meeting", "task", "follow_up", "note"}
)
VALID_ACTIVITY_STATUSES = frozenset({"pending", "completed", "cancelled"})


class ActivityCreate(BaseModel):
    activity_type: str
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    lead_public_id: str | None = None
    opportunity_public_id: str | None = None
    owner_user_public_id: str | None = None
    due_at: datetime | None = None

    @field_validator("activity_type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_ACTIVITY_TYPES:
            raise ValueError("Tipo de atividade inválido.")
        return normalized

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ActivityUpdate(BaseModel):
    activity_type: str | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    owner_user_public_id: str | None = None
    due_at: datetime | None = None

    @field_validator("activity_type")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in VALID_ACTIVITY_TYPES:
            raise ValueError("Tipo de atividade inválido.")
        return normalized

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())


class ActivityRead(BaseModel):
    public_id: str
    activity_type: str
    title: str
    description: str | None
    status: str
    due_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    lead_public_id: str | None
    opportunity_public_id: str | None
    owner_user_public_id: str | None
    created_at: datetime
    updated_at: datetime


class PendingActivityRead(ActivityRead):
    overdue: bool


class ActivityCardRead(ActivityRead):
    lead_name: str | None
    opportunity_title: str | None
    owner_name: str | None
    overdue: bool


class ActivityPageRead(BaseModel):
    items: list[ActivityCardRead]
    total: int
    page: int
    page_size: int
    total_pages: int
