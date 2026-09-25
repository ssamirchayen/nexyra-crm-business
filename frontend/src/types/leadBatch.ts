export type LeadBatchOwnerMode = "keep" | "assign" | "clear";

export type LeadBatchRequest = {
  lead_public_ids: string[];
  status: string | null;
  priority: string | null;
  owner_mode: LeadBatchOwnerMode;
  owner_user_public_id: string | null;
  active: boolean | null;
  dry_run: boolean;
};

export type LeadBatchItem = {
  lead_public_id: string;
  lead_name: string;
  changed: boolean;
  changed_fields: string[];
  before_status: string;
  after_status: string;
  before_priority: string;
  after_priority: string;
  before_owner_user_public_id: string | null;
  after_owner_user_public_id: string | null;
  before_active: boolean;
  after_active: boolean;
};

export type LeadBatchResult = {
  dry_run: boolean;
  requested: number;
  found: number;
  changed: number;
  unchanged: number;
  items: LeadBatchItem[];
};
