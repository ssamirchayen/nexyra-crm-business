export type RecommendationUrgency = "critical" | "high" | "medium" | "low";

export type RecommendationAction =
  | "assign_owner"
  | "reply_whatsapp"
  | "first_contact"
  | "follow_up"
  | "recover_opportunity"
  | "reengage"
  | "enroll_cadence"
  | "advance_opportunity"
  | "review_lead";

export type RecommendationChannel = "whatsapp" | "phone" | "email" | "manual";

export type LeadRecommendationMetrics = {
  total_leads: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  awaiting_reply: number;
  overdue_followups: number;
  unassigned: number;
  opportunities_at_risk: number;
};

export type LeadRecommendationItem = {
  lead_public_id: string;
  lead_name: string;
  interest: string | null;
  status: string;
  priority: string;
  source: string;
  owner_user_public_id: string | null;
  owner_name: string | null;
  action: RecommendationAction;
  action_title: string;
  urgency: RecommendationUrgency;
  score: number;
  suggested_channel: RecommendationChannel;
  suggested_contact_window: string | null;
  reasons: string[];
  reason_codes: string[];
  last_contact_at: string | null;
  last_whatsapp_at: string | null;
  awaiting_whatsapp_reply: boolean;
  active_cadence: boolean;
  open_opportunity_public_id: string | null;
  open_opportunity_stage: string | null;
  open_opportunity_value: number | null;
  opportunity_at_risk: boolean;
};

export type LeadRecommendationBoard = {
  generated_at: string;
  suggested_contact_window: string | null;
  metrics: LeadRecommendationMetrics;
  items: LeadRecommendationItem[];
};
