from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Lead, User, WorkspaceMembership


class LeadRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values: object) -> Lead:
        lead = Lead(**values)
        self.db.add(lead)
        self.db.flush()
        return lead

    def save(self, lead: Lead) -> Lead:
        self.db.add(lead)
        self.db.flush()
        return lead

    def get_by_public_id(
        self,
        *,
        workspace_id: int,
        public_id: str,
    ) -> Lead | None:
        statement = select(Lead).where(
            Lead.workspace_id == workspace_id,
            Lead.public_id == public_id,
        )
        return self.db.scalar(statement)

    def list_for_workspace(
        self,
        workspace_id: int,
    ) -> list[Lead]:
        statement = (
            select(Lead)
            .where(Lead.workspace_id == workspace_id)
            .order_by(Lead.id.desc())
        )
        return list(self.db.scalars(statement).all())

    def search_for_workspace(
        self,
        *,
        workspace_id: int,
        query: str | None,
        status: str | None,
        priority: str | None,
        source: str | None,
        channel: str | None,
        campaign: str | None,
        owner_membership_id: int | None,
        only_unassigned: bool,
        active: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Lead], int]:
        conditions = [Lead.workspace_id == workspace_id]

        if query:
            pattern = f"%{query.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(Lead.name).like(pattern),
                    func.lower(func.coalesce(Lead.phone, "")).like(pattern),
                    func.lower(func.coalesce(Lead.email, "")).like(pattern),
                    func.lower(func.coalesce(Lead.interest, "")).like(pattern),
                    func.lower(func.coalesce(Lead.campaign, "")).like(pattern),
                    func.lower(func.coalesce(Lead.external_id, "")).like(pattern),
                )
            )

        if status:
            normalized_status = status.strip().lower().replace(" ", "_")
            conditions.append(Lead.status == normalized_status)
        if priority:
            normalized_priority = priority.strip().lower().replace(" ", "_")
            conditions.append(Lead.priority == normalized_priority)
        if source:
            normalized_source = source.strip().lower().replace(" ", "_")
            conditions.append(Lead.source == normalized_source)
        if channel:
            normalized_channel = channel.strip().lower().replace(" ", "_")
            conditions.append(Lead.channel == normalized_channel)
        if campaign:
            conditions.append(
                func.lower(func.coalesce(Lead.campaign, "")).like(
                    f"%{campaign.strip().lower()}%"
                )
            )
        if owner_membership_id is not None:
            conditions.append(Lead.owner_membership_id == owner_membership_id)
        if only_unassigned:
            conditions.append(Lead.owner_membership_id.is_(None))
        if active is not None:
            conditions.append(Lead.active.is_(active))

        count_statement = select(func.count()).select_from(Lead).where(*conditions)
        total = int(self.db.scalar(count_statement) or 0)

        statement = (
            select(Lead)
            .where(*conditions)
            .order_by(Lead.id.desc())
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.scalars(statement).all()), total


    def active_loads_by_owner(self, workspace_id: int) -> dict[int, int]:
        statement = (
            select(Lead.owner_membership_id, func.count(Lead.id))
            .where(
                Lead.workspace_id == workspace_id,
                Lead.active.is_(True),
                Lead.owner_membership_id.is_not(None),
            )
            .group_by(Lead.owner_membership_id)
        )
        return {
            int(owner_id): int(count)
            for owner_id, count in self.db.execute(statement).all()
            if owner_id is not None
        }

    def active_counts(self, workspace_id: int) -> tuple[int, int]:
        total_statement = select(func.count(Lead.id)).where(
            Lead.workspace_id == workspace_id,
            Lead.active.is_(True),
        )
        unassigned_statement = select(func.count(Lead.id)).where(
            Lead.workspace_id == workspace_id,
            Lead.active.is_(True),
            Lead.owner_membership_id.is_(None),
        )
        return (
            int(self.db.scalar(total_statement) or 0),
            int(self.db.scalar(unassigned_statement) or 0),
        )

    def list_unassigned_active(
        self,
        *,
        workspace_id: int,
        limit: int,
    ) -> list[Lead]:
        statement = (
            select(Lead)
            .where(
                Lead.workspace_id == workspace_id,
                Lead.active.is_(True),
                Lead.owner_membership_id.is_(None),
            )
            .order_by(Lead.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def find_duplicate(
        self,
        *,
        workspace_id: int,
        normalized_phone: str | None,
        normalized_email: str | None,
        external_id: str | None,
        exclude_lead_id: int | None = None,
    ) -> Lead | None:
        conditions = []

        if normalized_phone:
            conditions.append(Lead.normalized_phone == normalized_phone)
        if normalized_email:
            conditions.append(Lead.normalized_email == normalized_email)
        if external_id:
            conditions.append(Lead.external_id == external_id)

        if not conditions:
            return None

        statement = select(Lead).where(
            Lead.workspace_id == workspace_id,
            or_(*conditions),
        )

        if exclude_lead_id is not None:
            statement = statement.where(Lead.id != exclude_lead_id)

        return self.db.scalar(statement.limit(1))

    def owner_user_public_id(
        self,
        owner_membership_id: int | None,
    ) -> str | None:
        if owner_membership_id is None:
            return None

        statement = (
            select(User.public_id)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.user_id == User.id,
            )
            .where(
                WorkspaceMembership.id == owner_membership_id,
            )
        )
        return self.db.scalar(statement)
