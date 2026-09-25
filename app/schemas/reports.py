from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ReportSourcePerformanceRead(BaseModel):
    source: str
    leads: int
    won_opportunities: int
    lost_opportunities: int
    conversion_rate: float
    won_value: Decimal
    lead_share_percent: float


class ReportMemberOptionRead(BaseModel):
    public_id: str
    name: str
    role: str


class ReportMemberPerformanceRead(BaseModel):
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


class ReportPipelineStageRead(BaseModel):
    stage: str
    opportunities: int
    value: Decimal
    share_percent: float


class ReportLossReasonRead(BaseModel):
    reason: str
    count: int
    percentage: float


class ReportInterestPerformanceRead(BaseModel):
    interest: str
    leads: int
    won_opportunities: int
    won_value: Decimal


class ReportRevenuePointRead(BaseModel):
    period_start: datetime
    period_end: datetime
    amount: Decimal
    won_opportunities: int


class ReportAnalyticsRead(BaseModel):
    workspace_public_id: str
    workspace_name: str
    generated_at: datetime
    period_days: int
    period_start: datetime
    period_end: datetime
    source_filter: str | None
    owner_user_public_id_filter: str | None

    total_leads: int
    opportunities_created: int
    open_opportunities: int
    open_pipeline_value: Decimal
    won_opportunities: int
    lost_opportunities: int
    conversion_rate: float
    won_value: Decimal
    average_ticket: Decimal

    activities_created: int
    completed_activities: int
    pending_activities: int
    overdue_activities: int

    available_sources: list[str]
    available_members: list[ReportMemberOptionRead]
    source_performance: list[ReportSourcePerformanceRead]
    member_performance: list[ReportMemberPerformanceRead]
    pipeline_stages: list[ReportPipelineStageRead]
    loss_reasons: list[ReportLossReasonRead]
    interest_performance: list[ReportInterestPerformanceRead]
    revenue_series: list[ReportRevenuePointRead]
