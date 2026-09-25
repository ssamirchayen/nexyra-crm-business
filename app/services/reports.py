from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Lead, Opportunity, User, WorkspaceMembership
from app.repositories import WorkspaceRepository
from app.services.workspace import WorkspaceNotFoundError


class ReportOwnerNotFoundError(ValueError):
    pass


class ReportsService:
    MAX_REVENUE_BUCKETS = 8

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
        return normalized is not None and start <= normalized < end

    @staticmethod
    def _conversion_rate(won: int, lost: int) -> float:
        closed = won + lost
        if closed == 0:
            return 0.0
        return round((won / closed) * 100, 2)

    @staticmethod
    def _percentage(value: int, total: int) -> float:
        if total == 0:
            return 0.0
        return round((value / total) * 100, 1)

    def _members(
        self,
        workspace_id: int,
    ) -> tuple[
        dict[int, tuple[str, str, str]],
        dict[str, int],
        list[dict[str, str]],
    ]:
        statement = (
            select(
                WorkspaceMembership.id,
                User.public_id,
                User.name,
                WorkspaceMembership.role,
            )
            .join(User, User.id == WorkspaceMembership.user_id)
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .order_by(User.name.asc())
        )
        rows = self.db.execute(statement).all()
        by_membership = {
            int(membership_id): (
                str(public_id),
                str(name),
                str(role),
            )
            for membership_id, public_id, name, role in rows
        }
        public_to_membership = {
            str(public_id): int(membership_id)
            for membership_id, public_id, _name, _role in rows
        }
        options = [
            {
                "public_id": str(public_id),
                "name": str(name),
                "role": str(role),
            }
            for _membership_id, public_id, name, role in rows
        ]
        return by_membership, public_to_membership, options

    @staticmethod
    def _lead_source(lead: Lead | None) -> str:
        if lead is None:
            return "outros"
        return (lead.source or "outros").strip() or "outros"

    def analytics(
        self,
        workspace_public_id: str,
        *,
        period_days: int = 30,
        source: str | None = None,
        owner_user_public_id: str | None = None,
    ) -> dict[str, object]:
        workspace = self.workspaces.get_by_public_id(workspace_public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {workspace_public_id}"
            )

        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)
        member_map, public_to_membership, member_options = self._members(workspace.id)

        owner_membership_id: int | None = None
        if owner_user_public_id:
            owner_membership_id = public_to_membership.get(owner_user_public_id)
            if owner_membership_id is None:
                raise ReportOwnerNotFoundError(
                    "O responsável informado não pertence a esta empresa."
                )

        all_leads = list(
            self.db.scalars(
                select(Lead)
                .where(Lead.workspace_id == workspace.id)
                .order_by(Lead.id.asc())
            ).all()
        )
        all_opportunities = list(
            self.db.scalars(
                select(Opportunity)
                .where(Opportunity.workspace_id == workspace.id)
                .order_by(Opportunity.id.asc())
            ).all()
        )
        all_activities = list(
            self.db.scalars(
                select(Activity)
                .where(Activity.workspace_id == workspace.id)
                .order_by(Activity.id.asc())
            ).all()
        )

        lead_by_id = {lead.id: lead for lead in all_leads}
        opportunity_by_id = {
            opportunity.id: opportunity for opportunity in all_opportunities
        }

        available_sources = sorted(
            {
                self._lead_source(lead)
                for lead in all_leads
                if lead.active
            }
        )

        def lead_matches(lead: Lead) -> bool:
            if source and self._lead_source(lead) != source:
                return False
            return (
                owner_membership_id is None
                or lead.owner_membership_id == owner_membership_id
            )

        def opportunity_matches(opportunity: Opportunity) -> bool:
            lead = lead_by_id.get(opportunity.lead_id)
            if source and self._lead_source(lead) != source:
                return False
            return (
                owner_membership_id is None
                or opportunity.owner_membership_id == owner_membership_id
            )

        def activity_source(activity: Activity) -> str:
            lead = lead_by_id.get(activity.lead_id) if activity.lead_id else None
            if lead is None and activity.opportunity_id:
                opportunity = opportunity_by_id.get(activity.opportunity_id)
                if opportunity is not None:
                    lead = lead_by_id.get(opportunity.lead_id)
            return self._lead_source(lead)

        def activity_matches(activity: Activity) -> bool:
            if source and activity_source(activity) != source:
                return False
            return (
                owner_membership_id is None
                or activity.owner_membership_id == owner_membership_id
            )

        period_leads = [
            lead
            for lead in all_leads
            if lead.active
            and lead_matches(lead)
            and self._in_period(lead.created_at, period_start, now)
        ]
        period_created_opportunities = [
            item
            for item in all_opportunities
            if opportunity_matches(item)
            and self._in_period(item.created_at, period_start, now)
        ]
        won_opportunities = [
            item
            for item in all_opportunities
            if item.status == "won"
            and opportunity_matches(item)
            and self._in_period(item.won_at, period_start, now)
        ]
        lost_opportunities = [
            item
            for item in all_opportunities
            if item.status == "lost"
            and opportunity_matches(item)
            and self._in_period(item.lost_at, period_start, now)
        ]
        open_opportunities = [
            item
            for item in all_opportunities
            if item.status == "open" and opportunity_matches(item)
        ]

        won_value = sum(
            (item.value_amount for item in won_opportunities),
            start=Decimal("0.00"),
        )
        open_pipeline_value = sum(
            (item.value_amount for item in open_opportunities),
            start=Decimal("0.00"),
        )
        average_ticket = (
            won_value / len(won_opportunities)
            if won_opportunities
            else Decimal("0.00")
        )

        period_activities = [
            item
            for item in all_activities
            if activity_matches(item)
            and self._in_period(item.created_at, period_start, now)
        ]
        completed_activities = [
            item
            for item in all_activities
            if item.status == "completed"
            and activity_matches(item)
            and self._in_period(item.completed_at, period_start, now)
        ]
        pending_activities = [
            item
            for item in all_activities
            if item.status == "pending" and activity_matches(item)
        ]
        overdue_activities = [
            item
            for item in pending_activities
            if self._as_utc(item.due_at) is not None
            and self._as_utc(item.due_at) < now
        ]

        source_lead_counts = Counter(
            self._lead_source(lead) for lead in period_leads
        )
        source_won: dict[str, list[Opportunity]] = defaultdict(list)
        source_lost: dict[str, list[Opportunity]] = defaultdict(list)
        for item in won_opportunities:
            source_won[self._lead_source(lead_by_id.get(item.lead_id))].append(item)
        for item in lost_opportunities:
            source_lost[self._lead_source(lead_by_id.get(item.lead_id))].append(item)

        source_codes = sorted(
            set(source_lead_counts) | set(source_won) | set(source_lost),
            key=lambda code: (
                -source_lead_counts.get(code, 0),
                code,
            ),
        )
        source_performance = []
        for code in source_codes:
            won_items = source_won.get(code, [])
            lost_items = source_lost.get(code, [])
            source_performance.append(
                {
                    "source": code,
                    "leads": source_lead_counts.get(code, 0),
                    "won_opportunities": len(won_items),
                    "lost_opportunities": len(lost_items),
                    "conversion_rate": self._conversion_rate(
                        len(won_items),
                        len(lost_items),
                    ),
                    "won_value": sum(
                        (item.value_amount for item in won_items),
                        start=Decimal("0.00"),
                    ),
                    "lead_share_percent": self._percentage(
                        source_lead_counts.get(code, 0),
                        len(period_leads),
                    ),
                }
            )

        member_performance = []
        for membership_id, (public_id, name, role) in member_map.items():
            if owner_membership_id is not None and membership_id != owner_membership_id:
                continue

            member_leads = [
                lead
                for lead in period_leads
                if lead.owner_membership_id == membership_id
            ]
            member_open = [
                item
                for item in open_opportunities
                if item.owner_membership_id == membership_id
            ]
            member_won = [
                item
                for item in won_opportunities
                if item.owner_membership_id == membership_id
            ]
            member_lost = [
                item
                for item in lost_opportunities
                if item.owner_membership_id == membership_id
            ]
            member_completed = [
                item
                for item in completed_activities
                if item.owner_membership_id == membership_id
            ]
            member_won_value = sum(
                (item.value_amount for item in member_won),
                start=Decimal("0.00"),
            )
            member_performance.append(
                {
                    "public_id": public_id,
                    "name": name,
                    "role": role,
                    "leads": len(member_leads),
                    "open_opportunities": len(member_open),
                    "won_opportunities": len(member_won),
                    "lost_opportunities": len(member_lost),
                    "conversion_rate": self._conversion_rate(
                        len(member_won),
                        len(member_lost),
                    ),
                    "won_value": member_won_value,
                    "average_ticket": (
                        member_won_value / len(member_won)
                        if member_won
                        else Decimal("0.00")
                    ),
                    "completed_activities": len(member_completed),
                }
            )
        member_performance.sort(
            key=lambda item: (
                -Decimal(item["won_value"]),
                -float(item["conversion_rate"]),
                str(item["name"]),
            )
        )

        stage_counts = Counter(item.stage for item in open_opportunities)
        stage_values: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for item in open_opportunities:
            stage_values[item.stage] += item.value_amount
        pipeline_stages = [
            {
                "stage": stage,
                "opportunities": count,
                "value": stage_values[stage],
                "share_percent": self._percentage(
                    count,
                    len(open_opportunities),
                ),
            }
            for stage, count in stage_counts.most_common()
        ]

        loss_counts = Counter(
            (item.loss_reason or "Não informado").strip() or "Não informado"
            for item in lost_opportunities
        )
        loss_reasons = [
            {
                "reason": reason,
                "count": count,
                "percentage": self._percentage(
                    count,
                    len(lost_opportunities),
                ),
            }
            for reason, count in loss_counts.most_common(8)
        ]

        interest_leads = Counter(
            (lead.interest or "Não informado").strip() or "Não informado"
            for lead in period_leads
        )
        interest_won_count: Counter[str] = Counter()
        interest_won_value: dict[str, Decimal] = defaultdict(
            lambda: Decimal("0.00")
        )
        for item in won_opportunities:
            lead = lead_by_id.get(item.lead_id)
            interest = (
                (lead.interest if lead else None) or "Não informado"
            ).strip() or "Não informado"
            interest_won_count[interest] += 1
            interest_won_value[interest] += item.value_amount

        interest_codes = sorted(
            set(interest_leads) | set(interest_won_count),
            key=lambda value: (
                -interest_won_value[value],
                -interest_leads[value],
                value,
            ),
        )
        interest_performance = [
            {
                "interest": interest,
                "leads": interest_leads[interest],
                "won_opportunities": interest_won_count[interest],
                "won_value": interest_won_value[interest],
            }
            for interest in interest_codes[:10]
        ]

        bucket_days = max(1, (period_days + self.MAX_REVENUE_BUCKETS - 1) // self.MAX_REVENUE_BUCKETS)
        revenue_series = []
        cursor = period_start
        while cursor < now:
            bucket_end = min(cursor + timedelta(days=bucket_days), now)
            bucket_items = [
                item
                for item in won_opportunities
                if self._in_period(item.won_at, cursor, bucket_end)
            ]
            revenue_series.append(
                {
                    "period_start": cursor,
                    "period_end": bucket_end,
                    "amount": sum(
                        (item.value_amount for item in bucket_items),
                        start=Decimal("0.00"),
                    ),
                    "won_opportunities": len(bucket_items),
                }
            )
            cursor = bucket_end

        return {
            "workspace_public_id": workspace.public_id,
            "workspace_name": workspace.name,
            "generated_at": now,
            "period_days": period_days,
            "period_start": period_start,
            "period_end": now,
            "source_filter": source,
            "owner_user_public_id_filter": owner_user_public_id,
            "total_leads": len(period_leads),
            "opportunities_created": len(period_created_opportunities),
            "open_opportunities": len(open_opportunities),
            "open_pipeline_value": open_pipeline_value,
            "won_opportunities": len(won_opportunities),
            "lost_opportunities": len(lost_opportunities),
            "conversion_rate": self._conversion_rate(
                len(won_opportunities),
                len(lost_opportunities),
            ),
            "won_value": won_value,
            "average_ticket": average_ticket,
            "activities_created": len(period_activities),
            "completed_activities": len(completed_activities),
            "pending_activities": len(pending_activities),
            "overdue_activities": len(overdue_activities),
            "available_sources": available_sources,
            "available_members": member_options,
            "source_performance": source_performance,
            "member_performance": member_performance,
            "pipeline_stages": pipeline_stages,
            "loss_reasons": loss_reasons,
            "interest_performance": interest_performance,
            "revenue_series": revenue_series,
        }
