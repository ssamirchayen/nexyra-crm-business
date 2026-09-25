from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DashboardSourceRead(BaseModel):
    source: str
    count: int
    percentage: float


class DashboardRecentLeadRead(BaseModel):
    public_id: str
    name: str
    source: str
    interest: str | None
    status: str
    priority: str
    owner_user_public_id: str | None
    owner_name: str | None
    created_at: datetime


class DashboardActivityRead(BaseModel):
    public_id: str
    activity_type: str
    title: str
    due_at: datetime | None
    overdue: bool
    lead_public_id: str | None
    owner_user_public_id: str | None
    owner_name: str | None


class DashboardRevenuePointRead(BaseModel):
    period_start: datetime
    period_end: datetime
    amount: Decimal
    won_opportunities: int


class DashboardSummaryRead(BaseModel):
    workspace_public_id: str
    workspace_name: str
    workspace_segment: str
    period_days: int
    generated_at: datetime

    leads_in_period: int
    leads_previous_period: int
    leads_trend_percent: float | None

    open_pipeline_value: Decimal
    open_opportunities: int

    conversion_rate: float
    previous_conversion_rate: float
    conversion_delta_pp: float

    won_value_in_period: Decimal
    average_won_value_in_period: Decimal
    won_opportunities_in_period: int
    lost_opportunities_in_period: int

    source_distribution: list[DashboardSourceRead]
    recent_leads: list[DashboardRecentLeadRead]
    upcoming_activities: list[DashboardActivityRead]
    revenue_series: list[DashboardRevenuePointRead]


class DashboardOperationalMemberRead(BaseModel):
    public_id: str
    name: str
    role: str


class DashboardOperationalSlaRead(BaseModel):
    total_attention: int
    awaiting_first_contact: int
    warning: int
    breached: int
    overdue_followups: int
    due_soon_followups: int
    stale_leads: int
    attention_share_percent: float


class DashboardOperationalRecommendationsRead(BaseModel):
    total: int
    critical: int
    high: int
    awaiting_reply: int
    opportunities_at_risk: int


class DashboardOperationalWhatsAppRead(BaseModel):
    inbound: int
    outbound: int
    sent: int
    delivered: int
    read: int
    failed: int
    delivery_rate: float
    read_rate: float


class DashboardOperationalCadencesRead(BaseModel):
    active_enrollments: int
    active_leads: int
    completed_in_period: int
    cancelled_in_period: int
    coverage_percent: float


class DashboardOperationalBottleneckRead(BaseModel):
    code: str
    title: str
    count: int
    severity: str
    route: str


class DashboardOperationalPipelineStageRead(BaseModel):
    stage: str
    opportunities: int
    value: Decimal
    share_percent: float


class DashboardOperationalMemberPerformanceRead(BaseModel):
    public_id: str
    name: str
    role: str
    leads: int
    open_opportunities: int
    won_opportunities: int
    lost_opportunities: int
    conversion_rate: float
    won_value: Decimal
    average_ticket: Decimal
    completed_activities: int


class DashboardOperationalRead(BaseModel):
    workspace_public_id: str
    workspace_name: str
    generated_at: datetime
    period_days: int
    period_start: datetime
    period_end: datetime
    owner_user_public_id_filter: str | None
    available_members: list[DashboardOperationalMemberRead]

    active_leads: int
    leads_created: int
    high_priority_leads: int
    unassigned_leads: int
    open_opportunities: int
    open_pipeline_value: Decimal
    conversion_rate: float
    won_value: Decimal
    pending_activities: int
    overdue_activities: int

    sla: DashboardOperationalSlaRead
    recommendations: DashboardOperationalRecommendationsRead
    whatsapp: DashboardOperationalWhatsAppRead
    cadences: DashboardOperationalCadencesRead
    bottlenecks: list[DashboardOperationalBottleneckRead]
    pipeline_stages: list[DashboardOperationalPipelineStageRead]
    member_performance: list[DashboardOperationalMemberPerformanceRead]
