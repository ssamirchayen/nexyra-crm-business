from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RecommendationUrgency = Literal["critical", "high", "medium", "low"]
RecommendationAction = Literal[
    "assign_owner",
    "reply_whatsapp",
    "first_contact",
    "follow_up",
    "recover_opportunity",
    "reengage",
    "enroll_cadence",
    "advance_opportunity",
    "review_lead",
]
RecommendationChannel = Literal["whatsapp", "phone", "email", "manual"]


class LeadRecommendationMetricsRead(BaseModel):
    total_leads: int
    critical: int
    high: int
    medium: int
    low: int
    awaiting_reply: int
    overdue_followups: int
    unassigned: int
    opportunities_at_risk: int


class LeadRecommendationItemRead(BaseModel):
    lead_public_id: str
    lead_name: str
    interest: str | None
    status: str
    priority: str
    source: str
    owner_user_public_id: str | None
    owner_name: str | None
    action: RecommendationAction
    action_title: str
    urgency: RecommendationUrgency
    score: int
    suggested_channel: RecommendationChannel
    suggested_contact_window: str | None
    reasons: list[str]
    reason_codes: list[str]
    last_contact_at: datetime | None
    last_whatsapp_at: datetime | None
    awaiting_whatsapp_reply: bool
    active_cadence: bool
    open_opportunity_public_id: str | None
    open_opportunity_stage: str | None
    open_opportunity_value: float | None
    opportunity_at_risk: bool


class LeadRecommendationBoardRead(BaseModel):
    generated_at: datetime
    suggested_contact_window: str | None
    metrics: LeadRecommendationMetricsRead
    items: list[LeadRecommendationItemRead]
