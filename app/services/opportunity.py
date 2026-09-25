from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.audit import opportunity_snapshot
from app.models import Lead, Opportunity, OpportunityStageHistory
from app.repositories import (
    LeadRepository,
    OpportunityRepository,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
    WorkspaceSegmentConfigRepository,
)
from app.schemas import (
    OpportunityCreate,
    OpportunityLost,
    OpportunityMove,
    OpportunityUpdate,
    OpportunityWon,
)
from app.segments import get_segment_definition
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError


class OpportunityNotFoundError(ValueError):
    pass


class OpportunityLeadError(ValueError):
    pass


class OpportunityOwnerError(ValueError):
    pass


class OpportunityStageError(ValueError):
    pass


class OpportunityStateError(ValueError):
    pass


@dataclass(frozen=True)
class OpportunityView:
    opportunity: Opportunity
    lead_public_id: str
    owner_user_public_id: str | None


@dataclass(frozen=True)
class OpportunityCardView:
    opportunity: Opportunity
    lead: Lead
    owner_user_public_id: str | None
    owner_name: str | None


@dataclass(frozen=True)
class OpportunityPageView:
    items: list[OpportunityCardView]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class PipelineStageView:
    code: str
    opportunities: list[OpportunityCardView]
    total_count: int
    total_value: Decimal


@dataclass(frozen=True)
class PipelineBoardView:
    workspace_public_id: str
    pipeline: list[str]
    stages: list[PipelineStageView]
    open_opportunities: int
    total_pipeline_value: Decimal


@dataclass(frozen=True)
class OpportunityHistoryView:
    history: OpportunityStageHistory
    changed_by_user_public_id: str | None


class OpportunityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.opportunities = OpportunityRepository(db)
        self.leads = LeadRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.segment_configs = WorkspaceSegmentConfigRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {public_id}"
            )
        return workspace

    def _pipeline(self, workspace) -> list[str]:
        config = self.segment_configs.get_by_workspace_id(workspace.id)

        if config is not None:
            return list(config.pipeline)

        definition = get_segment_definition(workspace.segment)
        if definition is None:
            return ["novo"]

        return list(definition.pipeline)

    def _lead(self, workspace_id: int, lead_public_id: str):
        lead = self.leads.get_by_public_id(
            workspace_id=workspace_id,
            public_id=lead_public_id,
        )
        if lead is None:
            raise OpportunityLeadError(
                f"Lead não encontrado nesta empresa: {lead_public_id}"
            )
        return lead

    def _membership_id(
        self,
        *,
        workspace_id: int,
        user_public_id: str | None,
    ) -> int | None:
        if user_public_id is None:
            return None

        user = self.users.get_by_public_id(user_public_id)
        if user is None:
            raise OpportunityOwnerError(
                f"Usuário não encontrado: {user_public_id}"
            )

        membership = self.memberships.get(
            workspace_id=workspace_id,
            user_id=user.id,
        )

        if membership is None or not membership.active:
            raise OpportunityOwnerError(
                "O usuário não possui acesso ativo a esta empresa."
            )

        return membership.id

    def _filter_membership_id(
        self,
        *,
        workspace_id: int,
        user_public_id: str | None,
    ) -> int | None:
        if user_public_id is None:
            return None

        user = self.users.get_by_public_id(user_public_id)
        if user is None:
            return -1

        membership = self.memberships.get(
            workspace_id=workspace_id,
            user_id=user.id,
        )
        if membership is None:
            return -1

        return membership.id

    @staticmethod
    def _validate_stage(stage: str, pipeline: list[str]) -> None:
        if stage not in pipeline:
            raise OpportunityStageError(
                f"Etapa '{stage}' não pertence ao pipeline desta empresa."
            )

    def _view(self, opportunity: Opportunity) -> OpportunityView:
        return OpportunityView(
            opportunity=opportunity,
            lead_public_id=self.opportunities.lead_public_id(
                opportunity.lead_id
            ),
            owner_user_public_id=(
                self.opportunities.owner_user_public_id(
                    opportunity.owner_membership_id
                )
            ),
        )

    @staticmethod
    def _card_view(
        row: tuple[Opportunity, Lead, str | None, str | None],
    ) -> OpportunityCardView:
        opportunity, lead, owner_public_id, owner_name = row
        return OpportunityCardView(
            opportunity=opportunity,
            lead=lead,
            owner_user_public_id=owner_public_id,
            owner_name=owner_name,
        )

    def create(
        self,
        workspace_public_id: str,
        payload: OpportunityCreate,
    ) -> OpportunityView:
        workspace = self._workspace(workspace_public_id)
        lead = self._lead(
            workspace.id,
            payload.lead_public_id,
        )
        pipeline = self._pipeline(workspace)

        stage = payload.stage or pipeline[0]
        self._validate_stage(stage, pipeline)

        if payload.owner_user_public_id is not None:
            owner_membership_id = self._membership_id(
                workspace_id=workspace.id,
                user_public_id=payload.owner_user_public_id,
            )
        else:
            owner_membership_id = lead.owner_membership_id

        title = payload.title
        if title is None:
            title = lead.interest or f"Oportunidade - {lead.name}"

        opportunity = self.opportunities.create(
            workspace_id=workspace.id,
            lead_id=lead.id,
            owner_membership_id=owner_membership_id,
            title=title,
            value_amount=payload.value_amount,
            currency=payload.currency,
            stage=stage,
            status="open",
            expected_close_date=payload.expected_close_date,
        )

        self.opportunities.add_history(
            opportunity_id=opportunity.id,
            from_stage=None,
            to_stage=stage,
            changed_by_membership_id=None,
            note="Oportunidade criada.",
        )

        created_view = self._view(opportunity)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="opportunity",
            entity_public_id=opportunity.public_id,
            action="opportunity.created",
            after_data=opportunity_snapshot(
                opportunity,
                lead_public_id=created_view.lead_public_id,
                owner_user_public_id=created_view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(opportunity)

        return self._view(opportunity)

    def list_all(
        self,
        workspace_public_id: str,
    ) -> list[OpportunityView]:
        workspace = self._workspace(workspace_public_id)

        return [
            self._view(item)
            for item in self.opportunities.list_for_workspace(
                workspace.id
            )
        ]

    def search(
        self,
        workspace_public_id: str,
        *,
        query: str | None = None,
        stage: str | None = None,
        status: str | None = None,
        owner_user_public_id: str | None = None,
        only_unassigned: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> OpportunityPageView:
        workspace = self._workspace(workspace_public_id)
        owner_membership_id = self._filter_membership_id(
            workspace_id=workspace.id,
            user_public_id=owner_user_public_id,
        )

        rows, total = self.opportunities.card_rows(
            workspace_id=workspace.id,
            query=query,
            stage=stage,
            status=status,
            owner_membership_id=owner_membership_id,
            only_unassigned=only_unassigned,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        return OpportunityPageView(
            items=[self._card_view(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def pipeline_board(
        self,
        workspace_public_id: str,
        *,
        query: str | None = None,
        owner_user_public_id: str | None = None,
        only_unassigned: bool = False,
    ) -> PipelineBoardView:
        workspace = self._workspace(workspace_public_id)
        pipeline = self._pipeline(workspace)
        owner_membership_id = self._filter_membership_id(
            workspace_id=workspace.id,
            user_public_id=owner_user_public_id,
        )

        rows, _ = self.opportunities.card_rows(
            workspace_id=workspace.id,
            query=query,
            status="open",
            owner_membership_id=owner_membership_id,
            only_unassigned=only_unassigned,
        )

        cards = [self._card_view(row) for row in rows]
        extra_stages = sorted(
            {
                card.opportunity.stage
                for card in cards
                if card.opportunity.stage not in pipeline
            }
        )
        board_pipeline = [*pipeline, *extra_stages]
        grouped: dict[str, list[OpportunityCardView]] = {
            stage: [] for stage in board_pipeline
        }

        for card in cards:
            grouped.setdefault(card.opportunity.stage, []).append(card)

        stages = [
            PipelineStageView(
                code=stage,
                opportunities=grouped.get(stage, []),
                total_count=len(grouped.get(stage, [])),
                total_value=sum(
                    (
                        item.opportunity.value_amount
                        for item in grouped.get(stage, [])
                    ),
                    Decimal("0.00"),
                ),
            )
            for stage in board_pipeline
        ]

        return PipelineBoardView(
            workspace_public_id=workspace.public_id,
            pipeline=board_pipeline,
            stages=stages,
            open_opportunities=len(cards),
            total_pipeline_value=sum(
                (item.opportunity.value_amount for item in cards),
                Decimal("0.00"),
            ),
        )

    def get(
        self,
        workspace_public_id: str,
        opportunity_public_id: str,
    ) -> OpportunityView:
        workspace = self._workspace(workspace_public_id)

        opportunity = self.opportunities.get_by_public_id(
            workspace_id=workspace.id,
            public_id=opportunity_public_id,
        )

        if opportunity is None:
            raise OpportunityNotFoundError(
                f"Oportunidade não encontrada: {opportunity_public_id}"
            )

        return self._view(opportunity)

    def update(
        self,
        workspace_public_id: str,
        opportunity_public_id: str,
        payload: OpportunityUpdate,
    ) -> OpportunityView:
        workspace = self._workspace(workspace_public_id)

        opportunity = self.opportunities.get_by_public_id(
            workspace_id=workspace.id,
            public_id=opportunity_public_id,
        )

        if opportunity is None:
            raise OpportunityNotFoundError(
                f"Oportunidade não encontrada: {opportunity_public_id}"
            )

        before_view = self._view(opportunity)
        before_data = opportunity_snapshot(
            opportunity,
            lead_public_id=before_view.lead_public_id,
            owner_user_public_id=before_view.owner_user_public_id,
        )

        changes = payload.model_dump(exclude_unset=True)

        if "owner_user_public_id" in changes:
            opportunity.owner_membership_id = self._membership_id(
                workspace_id=workspace.id,
                user_public_id=changes.pop("owner_user_public_id"),
            )

        for field_name in (
            "title",
            "value_amount",
            "currency",
            "expected_close_date",
        ):
            if field_name in changes:
                setattr(
                    opportunity,
                    field_name,
                    changes[field_name],
                )

        self.opportunities.save(opportunity)

        after_view = self._view(opportunity)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="opportunity",
            entity_public_id=opportunity.public_id,
            action="opportunity.updated",
            before_data=before_data,
            after_data=opportunity_snapshot(
                opportunity,
                lead_public_id=after_view.lead_public_id,
                owner_user_public_id=after_view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(opportunity)

        return self._view(opportunity)

    def move(
        self,
        workspace_public_id: str,
        opportunity_public_id: str,
        payload: OpportunityMove,
    ) -> OpportunityView:
        workspace = self._workspace(workspace_public_id)

        opportunity = self.opportunities.get_by_public_id(
            workspace_id=workspace.id,
            public_id=opportunity_public_id,
        )

        if opportunity is None:
            raise OpportunityNotFoundError(
                f"Oportunidade não encontrada: {opportunity_public_id}"
            )

        if opportunity.status != "open":
            raise OpportunityStateError(
                "Oportunidades encerradas não podem mudar de etapa."
            )

        pipeline = self._pipeline(workspace)
        self._validate_stage(payload.to_stage, pipeline)

        changed_by_membership_id = self._membership_id(
            workspace_id=workspace.id,
            user_public_id=payload.changed_by_user_public_id,
        )

        before_view = self._view(opportunity)
        before_data = opportunity_snapshot(
            opportunity,
            lead_public_id=before_view.lead_public_id,
            owner_user_public_id=before_view.owner_user_public_id,
        )

        previous_stage = opportunity.stage
        opportunity.stage = payload.to_stage

        self.opportunities.save(opportunity)
        self.opportunities.add_history(
            opportunity_id=opportunity.id,
            from_stage=previous_stage,
            to_stage=payload.to_stage,
            changed_by_membership_id=changed_by_membership_id,
            note=payload.note,
        )

        after_view = self._view(opportunity)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="opportunity",
            entity_public_id=opportunity.public_id,
            action="opportunity.moved",
            actor_type=(
                "user"
                if changed_by_membership_id is not None
                else "system"
            ),
            actor_membership_id=changed_by_membership_id,
            before_data=before_data,
            after_data=opportunity_snapshot(
                opportunity,
                lead_public_id=after_view.lead_public_id,
                owner_user_public_id=after_view.owner_user_public_id,
            ),
            metadata={
                "from_stage": previous_stage,
                "to_stage": payload.to_stage,
            },
        )

        self.db.commit()
        self.db.refresh(opportunity)

        return self._view(opportunity)

    def mark_won(
        self,
        workspace_public_id: str,
        opportunity_public_id: str,
        payload: OpportunityWon,
    ) -> OpportunityView:
        workspace = self._workspace(workspace_public_id)

        opportunity = self.opportunities.get_by_public_id(
            workspace_id=workspace.id,
            public_id=opportunity_public_id,
        )

        if opportunity is None:
            raise OpportunityNotFoundError(
                f"Oportunidade não encontrada: {opportunity_public_id}"
            )

        if opportunity.status != "open":
            raise OpportunityStateError(
                "A oportunidade já está encerrada."
            )

        changed_by_membership_id = self._membership_id(
            workspace_id=workspace.id,
            user_public_id=payload.changed_by_user_public_id,
        )

        before_view = self._view(opportunity)
        before_data = opportunity_snapshot(
            opportunity,
            lead_public_id=before_view.lead_public_id,
            owner_user_public_id=before_view.owner_user_public_id,
        )

        opportunity.status = "won"
        opportunity.loss_reason = None
        opportunity.won_at = datetime.now(timezone.utc)
        opportunity.lost_at = None

        self.opportunities.save(opportunity)
        self.opportunities.add_history(
            opportunity_id=opportunity.id,
            from_stage=opportunity.stage,
            to_stage=opportunity.stage,
            changed_by_membership_id=changed_by_membership_id,
            note=payload.note or "Oportunidade marcada como ganha.",
        )

        after_view = self._view(opportunity)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="opportunity",
            entity_public_id=opportunity.public_id,
            action="opportunity.won",
            actor_type=(
                "user"
                if changed_by_membership_id is not None
                else "system"
            ),
            actor_membership_id=changed_by_membership_id,
            before_data=before_data,
            after_data=opportunity_snapshot(
                opportunity,
                lead_public_id=after_view.lead_public_id,
                owner_user_public_id=after_view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(opportunity)

        return self._view(opportunity)

    def mark_lost(
        self,
        workspace_public_id: str,
        opportunity_public_id: str,
        payload: OpportunityLost,
    ) -> OpportunityView:
        workspace = self._workspace(workspace_public_id)

        opportunity = self.opportunities.get_by_public_id(
            workspace_id=workspace.id,
            public_id=opportunity_public_id,
        )

        if opportunity is None:
            raise OpportunityNotFoundError(
                f"Oportunidade não encontrada: {opportunity_public_id}"
            )

        if opportunity.status != "open":
            raise OpportunityStateError(
                "A oportunidade já está encerrada."
            )

        changed_by_membership_id = self._membership_id(
            workspace_id=workspace.id,
            user_public_id=payload.changed_by_user_public_id,
        )

        before_view = self._view(opportunity)
        before_data = opportunity_snapshot(
            opportunity,
            lead_public_id=before_view.lead_public_id,
            owner_user_public_id=before_view.owner_user_public_id,
        )

        opportunity.status = "lost"
        opportunity.loss_reason = payload.reason
        opportunity.lost_at = datetime.now(timezone.utc)
        opportunity.won_at = None

        self.opportunities.save(opportunity)
        self.opportunities.add_history(
            opportunity_id=opportunity.id,
            from_stage=opportunity.stage,
            to_stage=opportunity.stage,
            changed_by_membership_id=changed_by_membership_id,
            note=payload.note or f"Perdida: {payload.reason}",
        )

        after_view = self._view(opportunity)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="opportunity",
            entity_public_id=opportunity.public_id,
            action="opportunity.lost",
            actor_type=(
                "user"
                if changed_by_membership_id is not None
                else "system"
            ),
            actor_membership_id=changed_by_membership_id,
            before_data=before_data,
            after_data=opportunity_snapshot(
                opportunity,
                lead_public_id=after_view.lead_public_id,
                owner_user_public_id=after_view.owner_user_public_id,
            ),
            metadata={
                "loss_reason": payload.reason,
            },
        )

        self.db.commit()
        self.db.refresh(opportunity)

        return self._view(opportunity)

    def history(
        self,
        workspace_public_id: str,
        opportunity_public_id: str,
    ) -> list[OpportunityHistoryView]:
        view = self.get(
            workspace_public_id,
            opportunity_public_id,
        )

        return [
            OpportunityHistoryView(
                history=item,
                changed_by_user_public_id=(
                    self.opportunities.history_changed_by_user_public_id(
                        item.changed_by_membership_id
                    )
                ),
            )
            for item in self.opportunities.history(
                view.opportunity.id
            )
        ]

    def metrics(
        self,
        workspace_public_id: str,
    ) -> dict[str, object]:
        workspace = self._workspace(workspace_public_id)
        return self.opportunities.metrics(workspace.id)
