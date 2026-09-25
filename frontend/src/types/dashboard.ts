export type Workspace = {
  public_id: string;
  name: string;
  slug: string;
  segment: string;
  active: boolean;
};

export type DashboardSource = {
  source: string;
  count: number;
  percentage: number;
};

export type DashboardRecentLead = {
  public_id: string;
  name: string;
  source: string;
  interest: string | null;
  status: string;
  priority: string;
  owner_user_public_id: string | null;
  owner_name: string | null;
  created_at: string;
};

export type DashboardActivity = {
  public_id: string;
  activity_type: string;
  title: string;
  due_at: string | null;
  overdue: boolean;
  lead_public_id: string | null;
  owner_user_public_id: string | null;
  owner_name: string | null;
};

export type DashboardRevenuePoint = {
  period_start: string;
  period_end: string;
  amount: string;
  won_opportunities: number;
};

export type DashboardSummary = {
  workspace_public_id: string;
  workspace_name: string;
  workspace_segment: string;
  period_days: number;
  generated_at: string;

  leads_in_period: number;
  leads_previous_period: number;
  leads_trend_percent: number | null;

  open_pipeline_value: string;
  open_opportunities: number;

  conversion_rate: number;
  previous_conversion_rate: number;
  conversion_delta_pp: number;

  won_value_in_period: string;
  average_won_value_in_period: string;
  won_opportunities_in_period: number;
  lost_opportunities_in_period: number;

  source_distribution: DashboardSource[];
  recent_leads: DashboardRecentLead[];
  upcoming_activities: DashboardActivity[];
  revenue_series: DashboardRevenuePoint[];
};
