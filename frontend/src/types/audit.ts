export type AuditActorType = "system" | "user" | "atlas" | "integration" | string;

export type AuditEvent = {
  public_id: string;
  actor_type: AuditActorType;
  actor_user_public_id: string | null;
  actor_user_name: string | null;
  actor_role: string | null;
  entity_type: string;
  entity_public_id: string;
  action: string;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AuditActorOption = {
  public_id: string;
  name: string;
  role: string;
};

export type AuditStats = {
  total_events: number;
  user_events: number;
  system_events: number;
  atlas_events: number;
  integration_events: number;
};

export type AuditEventPage = {
  items: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  stats: AuditStats;
  available_actor_types: string[];
  available_entity_types: string[];
  available_actions: string[];
  available_actors: AuditActorOption[];
};
