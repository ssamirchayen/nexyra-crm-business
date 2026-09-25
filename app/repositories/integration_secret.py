from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration_secret import IntegrationSecret


class IntegrationSecretRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_source_id(self, integration_source_id: int) -> IntegrationSecret | None:
        return self.db.scalar(
            select(IntegrationSecret).where(
                IntegrationSecret.integration_source_id == integration_source_id
            )
        )

    def upsert(
        self,
        *,
        integration_source_id: int,
        provider: str,
        encrypted_payload: str,
    ) -> IntegrationSecret:
        item = self.get_by_source_id(integration_source_id)
        if item is None:
            item = IntegrationSecret(
                integration_source_id=integration_source_id,
                provider=provider,
                encrypted_payload=encrypted_payload,
            )
            self.db.add(item)
        else:
            item.provider = provider
            item.encrypted_payload = encrypted_payload
            self.db.add(item)
        self.db.flush()
        return item

    def delete_for_source(self, integration_source_id: int) -> None:
        item = self.get_by_source_id(integration_source_id)
        if item is not None:
            self.db.delete(item)
            self.db.flush()
