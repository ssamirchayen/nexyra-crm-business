export type Lead = {
  public_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  external_id: string | null;
  interest: string | null;
  source: string;
  channel: string;
  campaign: string | null;
  message: string | null;
  status: string;
  priority: string;
  custom_fields: Record<string, unknown>;
  owner_user_public_id: string | null;
  consent: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type LeadPage = {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type LeadIntakeResult = {
  action: "created" | "duplicate_updated" | string;
  lead: Lead;
};

export type WorkspaceMember = {
  public_id: string;
  name: string;
  email: string;
  user_active: boolean;
  role: string;
  membership_active: boolean;
};

export type WorkspaceSegmentConfig = {
  segment_code: string;
  interest_label: string;
  pipeline: string[];
  custom_fields: string[];
};

export type LeadPayload = {
  name: string;
  phone: string | null;
  email: string | null;
  external_id: string | null;
  interest: string | null;
  source: string;
  channel: string;
  campaign: string | null;
  message: string | null;
  status: string | null;
  priority: string;
  custom_fields: Record<string, unknown>;
  owner_user_public_id: string | null;
  consent: boolean;
};

export type LeadFilters = {
  q: string;
  status: string;
  priority: string;
  source: string;
  channel: string;
  campaign: string;
  owner: string;
  active: "true" | "false" | "all";
};
