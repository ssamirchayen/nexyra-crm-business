import type { Workspace } from "./dashboard";

export type SegmentDefinition = {
  code: string;
  label: string;
  interest_label: string;
  pipeline: string[];
  custom_fields: string[];
};

export type WorkspaceSegmentConfig = {
  segment_code: string;
  interest_label: string;
  pipeline: string[];
  custom_fields: string[];
};

export type CompanySettingsForm = Pick<Workspace, "name" | "slug">;

export type CommercialSettingsForm = WorkspaceSegmentConfig;

export type IntegrationProvider = {
  code: string;
  label: string;
  description: string;
  category: string;
  availability: "available" | "connector_pending" | string;
  default_source: string;
  default_channel: string;
  supports_multiple: boolean;
  capabilities: string[];
};

export type IntegrationSource = {
  public_id: string;
  provider: string;
  name: string;
  source: string;
  channel: string;
  default_campaign: string | null;
  routing_config: Record<string, unknown>;
  provider_config: Record<string, unknown>;
  active: boolean;
  external_intake_enabled: boolean;
  intake_key_prefix: string | null;
  intake_count: number;
  last_intake_at: string | null;
  created_at: string;
  updated_at: string;
};

export type IntegrationOverview = {
  providers: IntegrationProvider[];
  sources: IntegrationSource[];
  active_sources: number;
  intake_endpoint: string;
};

export type IntegrationSourceForm = {
  provider: string;
  name: string;
  source: string;
  channel: string;
  default_campaign: string;
};

export type IntegrationCredential = {
  integration_public_id: string;
  intake_key: string;
  key_prefix: string;
  intake_endpoint: string;
  header_name: string;
};

export type MetaLeadAdsStatus = {
  integration_public_id: string;
  configured: boolean;
  server_ready: boolean;
  subscribed: boolean;
  page_id: string | null;
  form_ids: string[];
  interest_field: string | null;
  default_interest: string | null;
  graph_api_version: string;
  webhook_endpoint: string;
  token_hint: string | null;
};

export type MetaLeadAdsConnectionTest = {
  ok: boolean;
  page_id: string;
  page_name: string | null;
  graph_api_version: string;
};

export type MetaLeadAdsSubscription = {
  ok: boolean;
  page_id: string;
  subscribed: boolean;
};
export type WhatsAppStatus = {
  integration_public_id: string;
  configured: boolean;
  server_ready: boolean;
  subscribed: boolean;
  phone_number_id: string | null;
  business_account_id: string | null;
  display_phone_number: string | null;
  verified_name: string | null;
  default_interest: string | null;
  graph_api_version: string;
  webhook_endpoint: string;
  token_hint: string | null;
  recent_messages: number;
  onboarding_mode: string | null;
  coexistence: boolean;
  embedded_signup_connected: boolean;
};

export type WhatsAppConnectionTest = {
  ok: boolean;
  phone_number_id: string;
  display_phone_number: string | null;
  verified_name: string | null;
  quality_rating: string | null;
  graph_api_version: string;
};

export type WhatsAppSubscription = {
  ok: boolean;
  business_account_id: string;
  subscribed: boolean;
};

export type WhatsAppMessagePreview = {
  to: string;
  text: string;
  confirmation_token: string;
  expires_at: string;
};

export type WhatsAppMessageSendResult = {
  ok: boolean;
  message_public_id: string;
  provider_message_id: string;
  to: string;
  status: string;
  lead_public_id: string | null;
};

export type WhatsAppMessage = {
  public_id: string;
  provider_message_id: string;
  direction: string;
  message_type: string;
  from_phone: string | null;
  to_phone: string | null;
  body: string | null;
  status: string;
  error_code: string | null;
  error_message: string | null;
  provider_timestamp: string | null;
  created_at: string;
  updated_at: string;
};
export type WhatsAppEmbeddedSignupConfig = {
  enabled: boolean;
  app_id: string | null;
  config_id: string | null;
  graph_api_version: string;
  feature_type: string;
  required_webhook_fields: string[];
};

export type WhatsAppPhoneCandidate = {
  phone_number_id: string;
  display_phone_number: string | null;
  verified_name: string | null;
  quality_rating: string | null;
};

export type WhatsAppEmbeddedSignupResult = {
  ok: boolean;
  connected: boolean;
  selection_required: boolean;
  business_account_id: string;
  phone_number_id: string | null;
  display_phone_number: string | null;
  verified_name: string | null;
  subscribed: boolean;
  coexistence: boolean;
  candidates: WhatsAppPhoneCandidate[];
};

export type WhatsAppCoexistenceSyncResult = {
  ok: boolean;
  sync_type: "history" | "smb_app_state_sync";
  request_id: string | null;
};

export type WhatsAppTemplate = {
  name: string;
  language: string;
  status: string;
  category: string | null;
  body_text: string | null;
  parameter_count: number;
  supported: boolean;
  unsupported_reason: string | null;
};

export type WhatsAppTemplatePreview = {
  to: string;
  template_name: string;
  language_code: string;
  parameters: string[];
  rendered_text: string;
  confirmation_token: string;
  expires_at: string;
};
