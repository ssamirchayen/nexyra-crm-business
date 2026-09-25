from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.whatsapp_message import WhatsAppMessage


class WhatsAppMessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values: object) -> WhatsAppMessage:
        item = WhatsAppMessage(**values)
        self.db.add(item)
        self.db.flush()
        return item

    def save(self, item: WhatsAppMessage) -> WhatsAppMessage:
        self.db.add(item)
        self.db.flush()
        return item

    def get_by_provider_message_id(
        self,
        provider_message_id: str,
    ) -> WhatsAppMessage | None:
        return self.db.scalar(
            select(WhatsAppMessage).where(
                WhatsAppMessage.provider_message_id == provider_message_id
            )
        )

    def recent_for_source(
        self,
        *,
        integration_source_id: int,
        limit: int = 20,
    ) -> list[WhatsAppMessage]:
        statement = (
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.integration_source_id == integration_source_id
            )
            .order_by(WhatsAppMessage.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())
