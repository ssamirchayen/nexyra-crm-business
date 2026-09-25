export type InboxConversation = {
  conversation_key: string;
  channel: "whatsapp" | string;
  integration_public_id: string;
  integration_name: string;
  contact_phone: string;
  lead_public_id: string | null;
  lead_name: string | null;
  lead_status: string | null;
  lead_priority: string | null;
  owner_user_public_id: string | null;
  owner_name: string | null;
  last_message_public_id: string;
  last_message_direction: string;
  last_message_type: string;
  last_message_body: string | null;
  last_message_status: string;
  last_message_at: string;
  unread_count: number;
};

export type InboxMessage = {
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
  read: boolean;
};

export type InboxThread = {
  conversation: InboxConversation;
  messages: InboxMessage[];
};

export type InboxMarkReadResult = {
  ok: boolean;
  marked: number;
  conversation_key: string;
};
