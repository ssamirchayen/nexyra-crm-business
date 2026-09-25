from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Activity, Lead, Opportunity, User, WorkspaceMembership


class ActivityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values: object) -> Activity:
        activity = Activity(**values)
        self.db.add(activity)
        self.db.flush()
        return activity

    def save(self, activity: Activity) -> Activity:
        self.db.add(activity)
        self.db.flush()
        return activity

    def get(self, workspace_id: int, public_id: str) -> Activity | None:
        return self.db.scalar(
            select(Activity).where(
                Activity.workspace_id == workspace_id,
                Activity.public_id == public_id,
            )
        )

    def list_for_workspace(self, workspace_id: int) -> list[Activity]:
        statement = (
            select(Activity)
            .where(Activity.workspace_id == workspace_id)
            .order_by(Activity.id.desc())
        )
        return list(self.db.scalars(statement).all())

    def pending_for_workspace(self, workspace_id: int) -> list[Activity]:
        statement = (
            select(Activity)
            .where(
                Activity.workspace_id == workspace_id,
                Activity.status == "pending",
            )
            .order_by(
                Activity.due_at.is_(None),
                Activity.due_at.asc(),
                Activity.id.asc(),
            )
        )
        return list(self.db.scalars(statement).all())

    def activity_rows(
        self,
        *,
        workspace_id: int,
        query: str | None = None,
        activity_type: str | None = None,
        status: str | None = None,
        owner_membership_id: int | None = None,
        only_unassigned: bool = False,
        overdue: bool | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[
        list[
            tuple[
                Activity,
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
            ]
        ],
        int,
    ]:
        conditions = [Activity.workspace_id == workspace_id]

        if query:
            pattern = f"%{query.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(Activity.title).like(pattern),
                    func.lower(func.coalesce(Activity.description, "")).like(pattern),
                    func.lower(func.coalesce(Lead.name, "")).like(pattern),
                    func.lower(func.coalesce(Opportunity.title, "")).like(pattern),
                    func.lower(func.coalesce(User.name, "")).like(pattern),
                )
            )

        if activity_type:
            conditions.append(Activity.activity_type == activity_type.strip().lower())
        if status:
            conditions.append(Activity.status == status.strip().lower())
        if owner_membership_id is not None:
            conditions.append(Activity.owner_membership_id == owner_membership_id)
        if only_unassigned:
            conditions.append(Activity.owner_membership_id.is_(None))
        if due_from is not None:
            conditions.append(Activity.due_at >= due_from)
        if due_to is not None:
            conditions.append(Activity.due_at <= due_to)

        now = datetime.now(timezone.utc)
        if overdue is True:
            conditions.extend(
                (
                    Activity.status == "pending",
                    Activity.due_at.is_not(None),
                    Activity.due_at < now,
                )
            )
        elif overdue is False:
            conditions.append(
                or_(
                    Activity.status != "pending",
                    Activity.due_at.is_(None),
                    Activity.due_at >= now,
                )
            )

        joins = (
            select(Activity.id)
            .outerjoin(Lead, Lead.id == Activity.lead_id)
            .outerjoin(Opportunity, Opportunity.id == Activity.opportunity_id)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == Activity.owner_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(*conditions)
        )
        total = int(
            self.db.scalar(select(func.count()).select_from(joins.subquery())) or 0
        )

        statement = (
            select(
                Activity,
                Lead.public_id,
                Lead.name,
                Opportunity.public_id,
                Opportunity.title,
                User.public_id,
                User.name,
            )
            .outerjoin(Lead, Lead.id == Activity.lead_id)
            .outerjoin(Opportunity, Opportunity.id == Activity.opportunity_id)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == Activity.owner_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(*conditions)
            .order_by(
                Activity.status != "pending",
                Activity.due_at.is_(None),
                Activity.due_at.asc(),
                Activity.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        rows = self.db.execute(statement).all()
        return [tuple(row) for row in rows], total

    def lead_public_id(self, lead_id: int | None) -> str | None:
        if lead_id is None:
            return None
        return self.db.scalar(select(Lead.public_id).where(Lead.id == lead_id))

    def opportunity_public_id(self, opportunity_id: int | None) -> str | None:
        if opportunity_id is None:
            return None
        return self.db.scalar(
            select(Opportunity.public_id).where(Opportunity.id == opportunity_id)
        )

    def owner_user_public_id(self, membership_id: int | None) -> str | None:
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
