from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Lead,
    Opportunity,
    OpportunityStageHistory,
    User,
    WorkspaceMembership,
)


class OpportunityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values: object) -> Opportunity:
        opportunity = Opportunity(**values)
        self.db.add(opportunity)
        self.db.flush()
        return opportunity

    def save(self, opportunity: Opportunity) -> Opportunity:
        self.db.add(opportunity)
        self.db.flush()
        return opportunity

    def get_by_public_id(
        self,
        *,
        workspace_id: int,
        public_id: str,
    ) -> Opportunity | None:
        statement = select(Opportunity).where(
            Opportunity.workspace_id == workspace_id,
            Opportunity.public_id == public_id,
        )
        return self.db.scalar(statement)

    def list_for_workspace(
        self,
        workspace_id: int,
    ) -> list[Opportunity]:
        statement = (
            select(Opportunity)
            .where(Opportunity.workspace_id == workspace_id)
            .order_by(Opportunity.id.desc())
        )
        return list(self.db.scalars(statement).all())

    def lead_public_id(self, lead_id: int) -> str:
        value = self.db.scalar(
            select(Lead.public_id).where(Lead.id == lead_id)
        )
        if value is None:
            raise ValueError("Lead vinculado à oportunidade não encontrado.")
        return value

    def owner_user_public_id(
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

    def card_rows(
        self,
        *,
        workspace_id: int,
        query: str | None = None,
        stage: str | None = None,
        status: str | None = None,
        owner_membership_id: int | None = None,
        only_unassigned: bool = False,
        offset: int | None = None,
        limit: int | None = None,
    ) -> tuple[list[tuple[Opportunity, Lead, str | None, str | None]], int]:
        conditions = [Opportunity.workspace_id == workspace_id]

        if query:
            pattern = f"%{query.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(Opportunity.title).like(pattern),
                    func.lower(Lead.name).like(pattern),
                    func.lower(func.coalesce(Lead.phone, "")).like(pattern),
                    func.lower(func.coalesce(Lead.email, "")).like(pattern),
                    func.lower(func.coalesce(Lead.interest, "")).like(pattern),
                )
            )

        if stage:
            normalized_stage = stage.strip().lower().replace(" ", "_")
            conditions.append(Opportunity.stage == normalized_stage)

        if status:
            normalized_status = status.strip().lower()
            conditions.append(Opportunity.status == normalized_status)

        if owner_membership_id is not None:
            conditions.append(
                Opportunity.owner_membership_id == owner_membership_id
            )

        if only_unassigned:
            conditions.append(Opportunity.owner_membership_id.is_(None))

        count_statement = (
            select(func.count(Opportunity.id))
            .select_from(Opportunity)
            .join(Lead, Lead.id == Opportunity.lead_id)
            .where(*conditions)
        )
        total = int(self.db.scalar(count_statement) or 0)

        statement = (
            select(
                Opportunity,
                Lead,
                User.public_id,
                User.name,
            )
            .join(Lead, Lead.id == Opportunity.lead_id)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == Opportunity.owner_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(*conditions)
            .order_by(Opportunity.id.desc())
        )

        if offset is not None:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        rows = self.db.execute(statement).all()
        return [
            (opportunity, lead, owner_public_id, owner_name)
            for opportunity, lead, owner_public_id, owner_name in rows
        ], total

    def add_history(
        self,
        *,
        opportunity_id: int,
        from_stage: str | None,
        to_stage: str,
        changed_by_membership_id: int | None,
        note: str | None,
    ) -> OpportunityStageHistory:
        item = OpportunityStageHistory(
            opportunity_id=opportunity_id,
            from_stage=from_stage,
            to_stage=to_stage,
            changed_by_membership_id=changed_by_membership_id,
            note=note,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def history(
        self,
        opportunity_id: int,
    ) -> list[OpportunityStageHistory]:
        statement = (
            select(OpportunityStageHistory)
            .where(
                OpportunityStageHistory.opportunity_id
                == opportunity_id
            )
            .order_by(OpportunityStageHistory.id.asc())
        )
        return list(self.db.scalars(statement).all())

    def history_changed_by_user_public_id(
        self,
        membership_id: int | None,
    ) -> str | None:
        return self.owner_user_public_id(membership_id)

    def metrics(
        self,
        workspace_id: int,
    ) -> dict[str, object]:
        rows = self.db.execute(
            select(
                Opportunity.status,
                func.count(Opportunity.id),
                func.coalesce(
                    func.sum(Opportunity.value_amount),
                    Decimal("0.00"),
                ),
            )
            .where(Opportunity.workspace_id == workspace_id)
            .group_by(Opportunity.status)
        ).all()

        counts = {
            "open": 0,
            "won": 0,
            "lost": 0,
        }
        values = {
            "open": Decimal("0.00"),
            "won": Decimal("0.00"),
            "lost": Decimal("0.00"),
        }

        for status, count, amount in rows:
            counts[status] = int(count)
            values[status] = Decimal(amount or 0)

        total = sum(counts.values())
        won = counts["won"]
        closed = counts["won"] + counts["lost"]

        conversion_rate = (
            round((won / closed) * 100, 2)
            if closed
            else 0.0
        )

        average_won_value = (
            values["won"] / won
            if won
            else Decimal("0.00")
        )

        return {
            "total_opportunities": total,
            "open_opportunities": counts["open"],
            "won_opportunities": counts["won"],
            "lost_opportunities": counts["lost"],
            "conversion_rate": conversion_rate,
            "total_pipeline_value": values["open"],
            "won_value": values["won"],
            "average_won_value": average_won_value,
        }
