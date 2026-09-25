from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IntegrationSource


class IntegrationSourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        workspace_id: int,
        provider: str,
        name: str,
        source: str,
        channel: str,
        default_campaign: str | None,
        routing_config: dict[str, object],
        provider_config: dict[str, object],
        active: bool,
    ) -> IntegrationSource:
        item = IntegrationSource(
            workspace_id=workspace_id,
            provider=provider,
            name=name,
            source=source,
            channel=channel,
            default_campaign=default_campaign,
            routing_config=routing_config,
            provider_config=provider_config,
            active=active,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def list_for_workspace(self, workspace_id: int) -> list[IntegrationSource]:
        statement = (
            select(IntegrationSource)
            .where(IntegrationSource.workspace_id == workspace_id)
            .order_by(
                IntegrationSource.active.desc(),
                IntegrationSource.name.asc(),
                IntegrationSource.id.asc(),
            )
        )
        return list(self.db.scalars(statement).all())

    def get_by_public_id(
        self,
        *,
        workspace_id: int,
        public_id: str,
    ) -> IntegrationSource | None:
        statement = select(IntegrationSource).where(
            IntegrationSource.workspace_id == workspace_id,
            IntegrationSource.public_id == public_id,
        )
        return self.db.scalar(statement)


    def get_global_by_public_id(self, public_id: str) -> IntegrationSource | None:
        statement = select(IntegrationSource).where(
            IntegrationSource.public_id == public_id
        )
        return self.db.scalar(statement)

    def list_active_by_provider(self, provider: str) -> list[IntegrationSource]:
        statement = (
            select(IntegrationSource)
            .where(
                IntegrationSource.provider == provider,
                IntegrationSource.active.is_(True),
            )
            .order_by(IntegrationSource.id.asc())
        )
        return list(self.db.scalars(statement).all())

    def get_by_name(
        self,
        *,
        workspace_id: int,
        name: str,
    ) -> IntegrationSource | None:
        statement = select(IntegrationSource).where(
            IntegrationSource.workspace_id == workspace_id,
            IntegrationSource.name == name,
        )
        return self.db.scalar(statement)

    def save(self, item: IntegrationSource) -> IntegrationSource:
        self.db.add(item)
        self.db.flush()
        return item
