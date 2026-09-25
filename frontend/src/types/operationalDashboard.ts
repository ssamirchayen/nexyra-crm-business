export type OperationalMember = {
  public_id: string;
  name: string;
  role: string;
};

export type OperationalSla = {
  total_attention: number;
  awaiting_first_contact: number;
  warning: number;
  breached: number;
  overdue_followups: number;
  due_soon_followups: number;
  stale_leads: number;
  attention_share_percent: number;
};

export type OperationalRecommendations = {
  total: number;
  critical: number;
  high: number;
  awaiting_reply: number;
  opportunities_at_risk: number;
};

export type OperationalWhatsApp = {
  inbound: number;
  outbound: number;
  sent: number;
  delivered: number;
  read: number;
  failed: number;
  delivery_rate: number;
  read_rate: number;
};

export type OperationalCadences = {
  active_enrollments: number;
  active_leads: number;
  completed_in_period: number;
  cancelled_in_period: number;
  coverage_percent: number;
};

export type OperationalBottleneck = {
  code: string;
  title: string;
  count: number;
  severity: "critical" | "warning" | string;
  route: string;
};

export type OperationalPipelineStage = {
  stage: string;
  opportunities: number;
  value: string;
  share_percent: number;
};

export type OperationalMemberPerformance = {
  public_id: string;
  name: string;
  role: string;
  leads: number;
  open_opportunities: number;
  won_opportunities: number;
  lost_opportunities: number;
  conversion_rate: number;
  won_value: string;
  average_ticket: string;
  completed_activities: number;
};

export type OperationalDashboard = {
  workspace_public_id: string;
  workspace_name: string;
  generated_at: string;
  period_days: number;
  period_start: string;
  period_end: string;
  owner_user_public_id_filter: string | null;
  available_members: OperationalMember[];

  active_leads: number;
  leads_created: number;
  high_priority_leads: number;
  unassigned_leads: number;
  open_opportunities: number;
  open_pipeline_value: string;
  conversion_rate: number;
  won_value: string;
  pending_activities: number;
  overdue_activities: number;

  sla: OperationalSla;
  recommendations: OperationalRecommendations;
  whatsapp: OperationalWhatsApp;
  cadences: OperationalCadences;
  bottlenecks: OperationalBottleneck[];
  pipeline_stages: OperationalPipelineStage[];
  member_performance: OperationalMemberPerformance[];
};
