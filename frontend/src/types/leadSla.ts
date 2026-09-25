export type LeadSlaState = "within_sla" | "warning" | "breached" | "contacted";

export type LeadSlaConfig = {
  enabled: boolean;
  first_response_minutes: number;
  warning_before_minutes: number;
  follow_up_due_hours: number;
  stale_lead_hours: number;
};

export type LeadSlaQueueItem = {
  lead_public_id: string;
  lead_name: string;
  phone: string | null;
  interest: string | null;
  status: string;
  priority: string;
  source: string;
  owner_user_public_id: string | null;
  owner_name: string | null;
  created_at: string;
  age_minutes: number;
  first_contact_at: string | null;
  first_response_minutes: number | null;
  sla_due_at: string;
  sla_state: LeadSlaState;
  last_contact_at: string | null;
  pending_followups: number;
  overdue_followups: number;
  next_followup_due_at: string | null;
  stale: boolean;
  score: number;
  reasons: string[];
};

export type LeadSlaQueueMetrics = {
  total_attention: number;
  awaiting_first_contact: number;
  sla_warning: number;
  sla_breached: number;
  overdue_followups: number;
  due_soon_followups: number;
  stale_leads: number;
  unassigned: number;
};

export type LeadSlaQueue = {
  config: LeadSlaConfig;
  metrics: LeadSlaQueueMetrics;
  items: LeadSlaQueueItem[];
};
