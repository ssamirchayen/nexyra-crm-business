from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    public_id: str
    actor_type: str
    actor_user_public_id: str | None
    actor_user_name: str | None = None
    actor_role: str | None = None
    entity_type: str
    entity_public_id: str
    action: str
    before_data: dict[str, object] | None
    after_data: dict[str, object] | None
    metadata: dict[str, object]
    created_at: datetime


class AuditActorOptionRead(BaseModel):
    public_id: str
    name: str
    role: str


class AuditStatsRead(BaseModel):
    total_events: int
    user_events: int
    system_events: int
    atlas_events: int
    integration_events: int


class AuditEventPageRead(BaseModel):
    items: list[AuditEventRead]
    total: int
    page: int
    page_size: int
    total_pages: int
    stats: AuditStatsRead
    available_actor_types: list[str]
    available_entity_types: list[str]
    available_actions: list[str]
    available_actors: list[AuditActorOptionRead]
