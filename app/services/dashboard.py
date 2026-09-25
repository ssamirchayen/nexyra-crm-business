from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Lead,
    Opportunity,
    User,
    WorkspaceMembership,
)
from app.repositories import WorkspaceRepository
from app.services.workspace import WorkspaceNotFoundError


class DashboardService:
    PERIOD_DAYS = 30
    REVENUE_BUCKET_DAYS = 7
    REVENUE_BUCKETS = 4
    RECENT_LEAD_LIMIT = 5
    UPCOMING_ACTIVITY_LIMIT = 5
    SOURCE_LIMIT = 5

    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _in_period(
        cls,
        value: datetime | None,
        start: datetime,
        end: datetime,
    ) -> bool:
        normalized = cls._as_utc(value)
        if normalized is None:
            return False
        return start <= normalized < end

    @staticmethod
    def _trend(current: int, previous: int) -> float | None:
        if previous == 0 and current == 0:
            return 0.0
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 1)

    @staticmethod
    def _conversion_rate(won: int, lost: int) -> float:
        closed = won + lost
        if closed == 0:
            return 0.0
        return round((won / closed) * 100, 2)

    def _member_map(
        self,
        workspace_id: int,
    ) -> dict[int, tuple[str, str]]:
        statement = (
            select(
                WorkspaceMembership.id,
                User.public_id,
                User.name,
            )
            .join(User, User.id == WorkspaceMembership.user_id)
            .where(WorkspaceMembership.workspace_id == workspace_id)
        )
        return {
            int(membership_id): (str(user_public_id), str(user_name))
            for membership_id, user_public_id, user_name in self.db.execute(
                statement
            ).all()
        }

    def summary(self, workspace_public_id: str) -> dict[str, object]:
        workspace = self.workspaces.get_by_public_id(workspace_public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {workspace_public_id}"
            )

        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=self.PERIOD_DAYS)
        previous_start = period_start - timedelta(days=self.PERIOD_DAYS)

        leads = list(
            self.db.scalars(
                select(Lead)
                .where(Lead.workspace_id == workspace.id)
                .order_by(Lead.id.desc())
            ).all()
        )
        opportunities = list(
            self.db.scalars(
                select(Opportunity)
                .where(Opportunity.workspace_id == workspace.id)
                .order_by(Opportunity.id.desc())
            ).all()
        )
        pending_activities = list(
            self.db.scalars(
                select(Activity)
                .where(
                    Activity.workspace_id == workspace.id,
                    Activity.status == "pending",
                )
                .order_by(Activity.id.desc())
            ).all()
        )

        member_map = self._member_map(workspace.id)
        lead_public_ids = {lead.id: lead.public_id for lead in leads}

        current_leads = [
            lead
            for lead in leads
            if self._in_period(lead.created_at, period_start, now)
        ]
        previous_leads = [
            lead
            for lead in leads
            if self._in_period(
                lead.created_at,
                previous_start,
                period_start,
            )
        ]

        current_won = [
            item
            for item in opportunities
            if item.status == "won"
            and self._in_period(item.won_at, period_start, now)
        ]
        current_lost = [
            item
            for item in opportunities
            if item.status == "lost"
            and self._in_period(item.lost_at, period_start, now)
        ]
        previous_won = [
            item
            for item in opportunities
            if item.status == "won"
            and self._in_period(
                item.won_at,
                previous_start,
                period_start,
            )
        ]
        previous_lost = [
            item
            for item in opportunities
            if item.status == "lost"
            and self._in_period(
                item.lost_at,
                previous_start,
                period_start,
            )
        ]

        conversion_rate = self._conversion_rate(
            len(current_won),
            len(current_lost),
        )
        previous_conversion_rate = self._conversion_rate(
            len(previous_won),
            len(previous_lost),
        )

        open_opportunities = [
            item for item in opportunities if item.status == "open"
        ]
        open_pipeline_value = sum(
            (item.value_amount for item in open_opportunities),
            start=Decimal("0.00"),
        )
        won_value = sum(
            (item.value_amount for item in current_won),
            start=Decimal("0.00"),
        )
        average_won_value = (
            won_value / len(current_won)
            if current_won
            else Decimal("0.00")
        )

        source_counts = Counter(
            lead.source or "outros" for lead in current_leads
        )
        source_total = sum(source_counts.values())
        source_distribution = [
            {
                "source": source,
                "count": count,
                "percentage": round((count / source_total) * 100, 1),
            }
            for source, count in source_counts.most_common(self.SOURCE_LIMIT)
        ]

        recent_leads: list[dict[str, object]] = []
        for lead in leads[: self.RECENT_LEAD_LIMIT]:
            owner = (
                member_map.get(lead.owner_membership_id)
                if lead.owner_membership_id is not None
                else None
            )
            recent_leads.append(
                {
                    "public_id": lead.public_id,
                    "name": lead.name,
                    "source": lead.source,
                    "interest": lead.interest,
                    "status": lead.status,
                    "priority": lead.priority,
                    "owner_user_public_id": owner[0] if owner else None,
                    "owner_name": owner[1] if owner else None,
                    "created_at": self._as_utc(lead.created_at),
                }
            )

        def activity_sort_key(activity: Activity) -> tuple[bool, datetime]:
            due_at = self._as_utc(activity.due_at)
            return (
                due_at is None,
                due_at or datetime.max.replace(tzinfo=timezone.utc),
            )

        sorted_activities = sorted(
            pending_activities,
            key=activity_sort_key,
        )[: self.UPCOMING_ACTIVITY_LIMIT]

        upcoming_activities: list[dict[str, object]] = []
        for activity in sorted_activities:
            owner = (
                member_map.get(activity.owner_membership_id)
                if activity.owner_membership_id is not None
                else None
            )
            due_at = self._as_utc(activity.due_at)
            upcoming_activities.append(
                {
                    "public_id": activity.public_id,
                    "activity_type": activity.activity_type,
                    "title": activity.title,
                    "due_at": due_at,
                    "overdue": due_at is not None and due_at < now,
                    "lead_public_id": (
                        lead_public_ids.get(activity.lead_id)
                        if activity.lead_id is not None
                        else None
                    ),
                    "owner_user_public_id": owner[0] if owner else None,
                    "owner_name": owner[1] if owner else None,
                }
            )

        revenue_series: list[dict[str, object]] = []
        series_start = now - timedelta(
            days=self.REVENUE_BUCKET_DAYS * self.REVENUE_BUCKETS
        )
        for index in range(self.REVENUE_BUCKETS):
            bucket_start = series_start + timedelta(
                days=self.REVENUE_BUCKET_DAYS * index
            )
            bucket_end = bucket_start + timedelta(
                days=self.REVENUE_BUCKET_DAYS
            )
            bucket_won = [
                item
                for item in opportunities
                if item.status == "won"
                and self._in_period(
                    item.won_at,
                    bucket_start,
                    bucket_end,
                )
            ]
            revenue_series.append(
                {
                    "period_start": bucket_start,
                    "period_end": bucket_end,
                    "amount": sum(
                        (item.value_amount for item in bucket_won),
                        start=Decimal("0.00"),
                    ),
                    "won_opportunities": len(bucket_won),
                }
            )

        return {
            "workspace_public_id": workspace.public_id,
            "workspace_name": workspace.name,
            "workspace_segment": workspace.segment,
            "period_days": self.PERIOD_DAYS,
            "generated_at": now,
            "leads_in_period": len(current_leads),
            "leads_previous_period": len(previous_leads),
            "leads_trend_percent": self._trend(
                len(current_leads),
                len(previous_leads),
            ),
            "open_pipeline_value": open_pipeline_value,
            "open_opportunities": len(open_opportunities),
            "conversion_rate": conversion_rate,
            "previous_conversion_rate": previous_conversion_rate,
            "conversion_delta_pp": round(
                conversion_rate - previous_conversion_rate,
                2,
            ),
            "won_value_in_period": won_value,
            "average_won_value_in_period": average_won_value,
            "won_opportunities_in_period": len(current_won),
            "lost_opportunities_in_period": len(current_lost),
            "source_distribution": source_distribution,
            "recent_leads": recent_leads,
            "upcoming_activities": upcoming_activities,
            "revenue_series": revenue_series,
        }
