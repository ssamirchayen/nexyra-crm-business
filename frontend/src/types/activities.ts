import type { Lead, WorkspaceMember } from "./leads";
import type { OpportunityCard } from "./opportunities";

export type ActivityType =
  | "call"
  | "whatsapp"
  | "email"
  | "meeting"
  | "task"
  | "follow_up"
  | "note";

export type ActivityStatus = "pending" | "completed" | "cancelled";

export type Activity = {
  public_id: string;
  activity_type: ActivityType;
  title: string;
  description: string | null;
  status: ActivityStatus;
  due_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  lead_public_id: string | null;
  opportunity_public_id: string | null;
  owner_user_public_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ActivityCard = Activity & {
  lead_name: string | null;
  opportunity_title: string | null;
  owner_name: string | null;
  overdue: boolean;
};

export type ActivityPage = {
  items: ActivityCard[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type ActivityPayload = {
  activity_type: ActivityType;
  title: string;
  description: string | null;
  lead_public_id: string | null;
  opportunity_public_id: string | null;
  owner_user_public_id: string | null;
  due_at: string | null;
};

export type ActivityUpdatePayload = {
  activity_type: ActivityType;
  title: string;
  description: string | null;
  owner_user_public_id: string | null;
  due_at: string | null;
};

export type ActivityFilters = {
  q: string;
  activity_type: string;
  status: string;
  owner: string;
  overdue: "all" | "true" | "false";
};

export type ActivityMetadata = {
  leads: Lead[];
  opportunities: OpportunityCard[];
  members: WorkspaceMember[];
};
