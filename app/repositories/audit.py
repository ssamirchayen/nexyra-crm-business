from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, User, WorkspaceMembership


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values: object) -> AuditEvent:
        event = AuditEvent(**values)
        self.db.add(event)
        self.db.flush()
        return event

    @staticmethod
    def _conditions(
        *,
        workspace_id: int,
        query: str | None = None,
        actor_type: str | None = None,
        actor_user_public_id: str | None = None,
        entity_type: str | None = None,
        entity_public_id: str | None = None,
        action: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[object]:
        conditions: list[object] = [AuditEvent.workspace_id == workspace_id]

        if query:
            pattern = f"%{query.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(AuditEvent.public_id).like(pattern),
                    func.lower(AuditEvent.actor_type).like(pattern),
                    func.lower(AuditEvent.entity_type).like(pattern),
                    func.lower(AuditEvent.entity_public_id).like(pattern),
                    func.lower(AuditEvent.action).like(pattern),
                    func.lower(func.coalesce(User.name, "")).like(pattern),
                    func.lower(func.coalesce(User.email, "")).like(pattern),
                )
            )

        if actor_type:
            conditions.append(AuditEvent.actor_type == actor_type.strip().lower())
        if actor_user_public_id:
            conditions.append(User.public_id == actor_user_public_id.strip())
        if entity_type:
            conditions.append(AuditEvent.entity_type == entity_type.strip().lower())
        if entity_public_id:
            conditions.append(
                func.lower(AuditEvent.entity_public_id).like(
                    f"%{entity_public_id.strip().lower()}%"
                )
            )
        if action:
            conditions.append(AuditEvent.action == action.strip().lower())
        if created_from is not None:
            conditions.append(AuditEvent.created_at >= created_from)
        if created_to is not None:
            conditions.append(AuditEvent.created_at <= created_to)

        return conditions

    @staticmethod
    def _base_statement():
        return (
            select(AuditEvent)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == AuditEvent.actor_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
        )

    def list_for_workspace(
        self,
        *,
        workspace_id: int,
        entity_type: str | None = None,
        entity_public_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        conditions = self._conditions(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            action=action,
        )
        statement = (
            self._base_statement()
            .where(*conditions)
            .order_by(AuditEvent.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def search_for_workspace(
        self,
        *,
        workspace_id: int,
        query: str | None = None,
        actor_type: str | None = None,
        actor_user_public_id: str | None = None,
        entity_type: str | None = None,
        entity_public_id: str | None = None,
        action: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[
        list[tuple[AuditEvent, str | None, str | None, str | None]],
        int,
        dict[str, int],
    ]:
        conditions = self._conditions(
            workspace_id=workspace_id,
            query=query,
            actor_type=actor_type,
            actor_user_public_id=actor_user_public_id,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            action=action,
            created_from=created_from,
            created_to=created_to,
        )

        count_statement = (
            select(func.count(AuditEvent.id))
            .select_from(AuditEvent)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == AuditEvent.actor_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(*conditions)
        )
        total = int(self.db.scalar(count_statement) or 0)

        actor_count_rows = self.db.execute(
            select(AuditEvent.actor_type, func.count(AuditEvent.id))
            .select_from(AuditEvent)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == AuditEvent.actor_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(*conditions)
            .group_by(AuditEvent.actor_type)
        ).all()
        actor_counts = {
            str(actor): int(count)
            for actor, count in actor_count_rows
        }

        statement = (
            select(
                AuditEvent,
                User.public_id,
                User.name,
                WorkspaceMembership.role,
            )
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == AuditEvent.actor_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(*conditions)
            .order_by(AuditEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = self.db.execute(statement).all()

        return [
            (event, user_public_id, user_name, role)
            for event, user_public_id, user_name, role in rows
        ], total, actor_counts

    def facets_for_workspace(
        self,
        *,
        workspace_id: int,
    ) -> tuple[list[str], list[str], list[str]]:
        actor_types = list(
            self.db.scalars(
                select(AuditEvent.actor_type)
                .where(AuditEvent.workspace_id == workspace_id)
                .distinct()
                .order_by(AuditEvent.actor_type.asc())
            ).all()
        )
        entity_types = list(
            self.db.scalars(
                select(AuditEvent.entity_type)
                .where(AuditEvent.workspace_id == workspace_id)
                .distinct()
                .order_by(AuditEvent.entity_type.asc())
            ).all()
        )
        actions = list(
            self.db.scalars(
                select(AuditEvent.action)
                .where(AuditEvent.workspace_id == workspace_id)
                .distinct()
                .order_by(AuditEvent.action.asc())
            ).all()
        )
        return actor_types, entity_types, actions

    def actor_user_public_id(
        self,
        membership_id: int | None,
    ) -> str | None:
        if membership_id is None:
            return None

        statement = (
            select(User.public_id)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.user_id == User.id,
            )
            .where(WorkspaceMembership.id == membership_id)
        )
        return self.db.scalar(statement)

    def actor_details(
        self,
        membership_id: int | None,
    ) -> tuple[str | None, str | None, str | None]:
        if membership_id is None:
            return None, None, None

        statement = (
            select(User.public_id, User.name, WorkspaceMembership.role)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.user_id == User.id,
            )
            .where(WorkspaceMembership.id == membership_id)
        )
        row = self.db.execute(statement).one_or_none()
        if row is None:
            return None, None, None
        return row[0], row[1], row[2]
