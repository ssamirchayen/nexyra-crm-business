export type TeamRole = "admin" | "manager" | "seller" | "operator";

export type RoleDefinition = {
  role: TeamRole;
  permissions: string[];
};

export type TeamMember = {
  public_id: string;
  name: string;
  email: string;
  user_active: boolean;
  role: TeamRole;
  membership_active: boolean;
  assigned_leads: number;
  open_opportunities: number;
  won_opportunities: number;
  lost_opportunities: number;
  conversion_rate: number;
  won_value: string;
  pending_activities: number;
  overdue_activities: number;
};

export type TeamSummary = {
  workspace_public_id: string;
  total_members: number;
  active_members: number;
  sellers: number;
  managers: number;
  operators: number;
  total_assigned_leads: number;
  total_open_opportunities: number;
  total_won_value: string;
  members: TeamMember[];
};

export type TeamMemberCreatePayload = {
  name: string;
  email: string;
  role: TeamRole;
  initial_password?: string;
};

export type TeamMemberUpdatePayload = {
  role?: TeamRole;
  active?: boolean;
};
