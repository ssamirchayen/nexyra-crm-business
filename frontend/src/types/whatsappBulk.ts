export type WhatsAppBulkRecipientPreview = {
  lead_public_id: string;
  lead_name: string;
  phone: string | null;
  eligible: boolean;
  reason: string;
  parameters: string[];
  rendered_text: string | null;
};

export type WhatsAppBulkPreviewRequest = {
  lead_public_ids: string[];
  integration_public_id: string;
  template_name: string;
  language_code: string;
  parameter_templates: string[];
};

export type WhatsAppBulkPreview = {
  requested: number;
  eligible: number;
  blocked: number;
  integration_public_id: string;
  template_name: string;
  language_code: string;
  parameter_templates: string[];
  confirmation_token: string;
  expires_at: string;
  recipients: WhatsAppBulkRecipientPreview[];
};

export type WhatsAppBulkSendItem = {
  lead_public_id: string;
  lead_name: string;
  phone: string | null;
  status: "sent" | "failed" | "blocked" | string;
  provider_message_id: string | null;
  error: string | null;
};

export type WhatsAppBulkSendResult = {
  requested: number;
  attempted: number;
  sent: number;
  failed: number;
  blocked: number;
  items: WhatsAppBulkSendItem[];
};
