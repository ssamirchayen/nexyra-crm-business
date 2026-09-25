export type ReportSourcePerformance = {
  source: string;
  leads: number;
  won_opportunities: number;
  lost_opportunities: number;
  conversion_rate: number;
  won_value: string;
  lead_share_percent: number;
};

export type ReportMemberOption = {
  public_id: string;
  name: string;
  role: string;
};

export type ReportMemberPerformance = ReportMemberOption & {
  leads: number;
  open_opportunities: number;
  won_opportunities: number;
  lost_opportunities: number;
  conversion_rate: number;
  won_value: string;
  average_ticket: string;
  completed_activities: number;
};

export type ReportPipelineStage = {
  stage: string;
  opportunities: number;
  value: string;
  share_percent: number;
};

export type ReportLossReason = {
  reason: string;
  count: number;
  percentage: number;
};

export type ReportInterestPerformance = {
  interest: string;
  leads: number;
  won_opportunities: number;
  won_value: string;
};

export type ReportRevenuePoint = {
  period_start: string;
  period_end: string;
  amount: string;
  won_opportunities: number;
};

export type ReportAnalytics = {
  workspace_public_id: string;
  workspace_name: string;
  generated_at: string;
  period_days: number;
  period_start: string;
  period_end: string;
  source_filter: string | null;
  owner_user_public_id_filter: string | null;

  total_leads: number;
  opportunities_created: number;
  open_opportunities: number;
  open_pipeline_value: string;
  won_opportunities: number;
  lost_opportunities: number;
  conversion_rate: number;
  won_value: string;
  average_ticket: string;

  activities_created: number;
  completed_activities: number;
  pending_activities: number;
  overdue_activities: number;

  available_sources: string[];
  available_members: ReportMemberOption[];
  source_performance: ReportSourcePerformance[];
  member_performance: ReportMemberPerformance[];
  pipeline_stages: ReportPipelineStage[];
  loss_reasons: ReportLossReason[];
  interest_performance: ReportInterestPerformance[];
  revenue_series: ReportRevenuePoint[];
};
