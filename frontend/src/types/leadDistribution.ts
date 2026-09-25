export type LeadDistributionStrategy = "least_loaded" | "round_robin";

export type LeadDistributionRule = {
  name: string;
  enabled: boolean;
  source: string | null;
  channel: string | null;
  interest_contains: string | null;
  campaign_contains: string | null;
  priorities: string[];
  eligible_user_public_ids: string[];
  strategy: LeadDistributionStrategy | null;
};

export type LeadDistributionConfig = {
  enabled: boolean;
  strategy: LeadDistributionStrategy;
  eligible_roles: string[];
  eligible_user_public_ids: string[];
  rules: LeadDistributionRule[];
};

export type LeadDistributionMember = {
  user_public_id: string;
  name: string;
  role: string;
  active: boolean;
  eligible: boolean;
  assigned_active_leads: number;
};

export type LeadDistributionSummary = {
  config: LeadDistributionConfig;
  members: LeadDistributionMember[];
  unassigned_active_leads: number;
  total_active_leads: number;
};

export type LeadDistributionAssignment = {
  lead_public_id: string;
  user_public_id: string;
  user_name: string;
  strategy: LeadDistributionStrategy;
  rule_name: string | null;
  previous_load: number;
};

export type LeadDistributionRunResult = {
  dry_run: boolean;
  scanned: number;
  assigned: number;
  skipped: number;
  assignments: LeadDistributionAssignment[];
};
