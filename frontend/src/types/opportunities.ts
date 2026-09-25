import type {
  Lead,
  WorkspaceMember,
  WorkspaceSegmentConfig,
} from "./leads";

export type OpportunityStatus = "open" | "won" | "lost";

export type OpportunityCard = {
  public_id: string;
  lead_public_id: string;
  lead_name: string;
  lead_phone: string | null;
  lead_email: string | null;
  lead_interest: string | null;
  owner_user_public_id: string | null;
  owner_name: string | null;
  title: string;
  value_amount: string;
  currency: string;
  stage: string;
  status: OpportunityStatus;
  expected_close_date: string | null;
  loss_reason: string | null;
  won_at: string | null;
  lost_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Opportunity = {
  public_id: string;
  lead_public_id: string;
  owner_user_public_id: string | null;
  title: string;
  value_amount: string;
  currency: string;
  stage: string;
  status: OpportunityStatus;
  expected_close_date: string | null;
  loss_reason: string | null;
  won_at: string | null;
  lost_at: string | null;
};

export type OpportunityPage = {
  items: OpportunityCard[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type PipelineStage = {
  code: string;
  total_count: number;
  total_value: string;
  opportunities: OpportunityCard[];
};

export type PipelineBoard = {
  workspace_public_id: string;
  pipeline: string[];
  open_opportunities: number;
  total_pipeline_value: string;
  stages: PipelineStage[];
};

export type OpportunityHistory = {
  from_stage: string | null;
  to_stage: string;
  changed_by_user_public_id: string | null;
  note: string | null;
  created_at: string;
};

export type OpportunityPayload = {
  lead_public_id: string;
  title: string | null;
  value_amount: string;
  currency: string;
  stage: string | null;
  owner_user_public_id: string | null;
  expected_close_date: string | null;
};

export type OpportunityUpdatePayload = {
  title: string | null;
  value_amount: string;
  currency: string;
  owner_user_public_id: string | null;
  expected_close_date: string | null;
};

export type OpportunityFormMetadata = {
  leads: Lead[];
  members: WorkspaceMember[];
  segmentConfig: WorkspaceSegmentConfig | null;
};
