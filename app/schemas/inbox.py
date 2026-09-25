from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class InboxConversationRead(BaseModel):
    conversation_key: str
    channel: str = "whatsapp"
    integration_public_id: str
    integration_name: str
    contact_phone: str
    lead_public_id: str | None
    lead_name: str | None
    lead_status: str | None
    lead_priority: str | None
    owner_user_public_id: str | None
    owner_name: str | None
    last_message_public_id: str
    last_message_direction: str
    last_message_type: str
    last_message_body: str | None
    last_message_status: str
    last_message_at: datetime
    unread_count: int = 0


class InboxMessageRead(BaseModel):
    public_id: str
    provider_message_id: str
    direction: str
    message_type: str
    from_phone: str | None
    to_phone: str | None
    body: str | None
    status: str
    error_code: str | None
    error_message: str | None
    provider_timestamp: datetime | None
    created_at: datetime
    updated_at: datetime
    read: bool


class InboxThreadRead(BaseModel):
    conversation: InboxConversationRead
    messages: list[InboxMessageRead]


class InboxMarkReadRead(BaseModel):
    ok: bool = True
    marked: int = 0
    conversation_key: str
