from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit import activity_snapshot
from app.models import Activity
from app.repositories import (
    ActivityRepository,
    LeadRepository,
    OpportunityRepository,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.schemas import ActivityCreate, ActivityUpdate
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError


class ActivityNotFoundError(ValueError):
    pass


class ActivityTargetError(ValueError):
    pass


class ActivityOwnerError(ValueError):
    pass


class ActivityStateError(ValueError):
    pass


@dataclass(frozen=True)
class ActivityView:
    activity: Activity
    lead_public_id: str | None
    opportunity_public_id: str | None
    owner_user_public_id: str | None


@dataclass(frozen=True)
class ActivityCardView:
    activity: Activity
    lead_public_id: str | None
    lead_name: str | None
    opportunity_public_id: str | None
    opportunity_title: str | None
    owner_user_public_id: str | None
    owner_name: str | None
    overdue: bool


@dataclass(frozen=True)
class ActivityPageView:
    items: list[ActivityCardView]
    total: int
    page: int
    page_size: int


class ActivityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activities = ActivityRepository(db)
        self.leads = LeadRepository(db)
        self.opportunities = OpportunityRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {public_id}"
            )
        return workspace

    def _owner_membership_id(
        self,
        *,
        workspace_id: int,
        user_public_id: str | None,
    ) -> int | None:
        if user_public_id is None:
            return None

        user = self.users.get_by_public_id(user_public_id)
        if user is None:
            raise ActivityOwnerError(
                f"Responsável não encontrado: {user_public_id}"
            )

        membership = self.memberships.get(
            workspace_id=workspace_id,
            user_id=user.id,
        )

        if membership is None or not membership.active:
            raise ActivityOwnerError(
                "O responsável não possui acesso ativo a esta empresa."
            )

        return membership.id

    def _resolve_targets(
        self,
        *,
        workspace_id: int,
        lead_public_id: str | None,
        opportunity_public_id: str | None,
    ) -> tuple[int | None, int | None]:
        lead = None
        opportunity = None

        if lead_public_id is not None:
            lead = self.leads.get_by_public_id(
                workspace_id=workspace_id,
                public_id=lead_public_id,
            )
            if lead is None:
                raise ActivityTargetError(
                    f"Lead não encontrado nesta empresa: {lead_public_id}"
                )

        if opportunity_public_id is not None:
            opportunity = self.opportunities.get_by_public_id(
                workspace_id=workspace_id,
                public_id=opportunity_public_id,
            )
            if opportunity is None:
                raise ActivityTargetError(
                    "Oportunidade não encontrada nesta empresa: "
                    f"{opportunity_public_id}"
                )

        if lead is None and opportunity is None:
            return None, None

        if opportunity is not None:
            if lead is None:
                lead_id = opportunity.lead_id
            elif opportunity.lead_id != lead.id:
                raise ActivityTargetError(
                    "A oportunidade informada não pertence ao lead informado."
                )
            else:
                lead_id = lead.id

            return lead_id, opportunity.id

        return lead.id if lead is not None else None, None

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def is_overdue(activity: Activity) -> bool:
        if activity.status != "pending" or activity.due_at is None:
            return False

        due_at = activity.due_at
        now = datetime.now(timezone.utc)

        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)

        return due_at < now

    def _view(self, activity: Activity) -> ActivityView:
        return ActivityView(
            activity=activity,
            lead_public_id=self.activities.lead_public_id(
                activity.lead_id
            ),
            opportunity_public_id=(
                self.activities.opportunity_public_id(
                    activity.opportunity_id
                )
            ),
            owner_user_public_id=(
                self.activities.owner_user_public_id(
                    activity.owner_membership_id
                )
            ),
        )

    def _card_view(
        self,
        row: tuple[
            Activity,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
        ],
    ) -> ActivityCardView:
        (
            activity,
            lead_public_id,
            lead_name,
            opportunity_public_id,
            opportunity_title,
            owner_user_public_id,
            owner_name,
        ) = row
        return ActivityCardView(
            activity=activity,
            lead_public_id=lead_public_id,
            lead_name=lead_name,
            opportunity_public_id=opportunity_public_id,
            opportunity_title=opportunity_title,
            owner_user_public_id=owner_user_public_id,
            owner_name=owner_name,
            overdue=self.is_overdue(activity),
        )

    def create(
        self,
        workspace_public_id: str,
        payload: ActivityCreate,
    ) -> ActivityView:
        workspace = self._workspace(workspace_public_id)

        lead_id, opportunity_id = self._resolve_targets(
            workspace_id=workspace.id,
            lead_public_id=payload.lead_public_id,
            opportunity_public_id=payload.opportunity_public_id,
        )

        owner_membership_id = self._owner_membership_id(
            workspace_id=workspace.id,
            user_public_id=payload.owner_user_public_id,
        )

        activity = self.activities.create(
            workspace_id=workspace.id,
            lead_id=lead_id,
            opportunity_id=opportunity_id,
            owner_membership_id=owner_membership_id,
            activity_type=payload.activity_type,
            title=payload.title,
            description=payload.description,
            status="pending",
            due_at=self._normalize_datetime(payload.due_at),
        )

        created_view = self._view(activity)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="activity",
            entity_public_id=activity.public_id,
            action="activity.created",
            after_data=activity_snapshot(
                activity,
                lead_public_id=created_view.lead_public_id,
                opportunity_public_id=(
                    created_view.opportunity_public_id
                ),
                owner_user_public_id=created_view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(activity)

        return self._view(activity)

    def get(
        self,
        workspace_public_id: str,
        activity_public_id: str,
    ) -> ActivityView:
        workspace = self._workspace(workspace_public_id)

        activity = self.activities.get(
            workspace.id,
            activity_public_id,
        )
        if activity is None:
            raise ActivityNotFoundError(
                f"Atividade não encontrada: {activity_public_id}"
            )

        return self._view(activity)

    def list_all(
        self,
        workspace_public_id: str,
    ) -> list[ActivityView]:
        workspace = self._workspace(workspace_public_id)

        return [
            self._view(item)
            for item in self.activities.list_for_workspace(
                workspace.id
            )
        ]

    def search(
        self,
        workspace_public_id: str,
        *,
        query: str | None = None,
        activity_type: str | None = None,
        status: str | None = None,
        owner_user_public_id: str | None = None,
        only_unassigned: bool = False,
        overdue: bool | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ActivityPageView:
        workspace = self._workspace(workspace_public_id)
        owner_membership_id = self._owner_membership_id(
            workspace_id=workspace.id,
            user_public_id=owner_user_public_id,
        )

        rows, total = self.activities.activity_rows(
            workspace_id=workspace.id,
            query=query,
            activity_type=activity_type,
            status=status,
            owner_membership_id=owner_membership_id,
            only_unassigned=only_unassigned,
            overdue=overdue,
            due_from=self._normalize_datetime(due_from),
            due_to=self._normalize_datetime(due_to),
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        return ActivityPageView(
            items=[self._card_view(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_for_lead(
        self,
        workspace_public_id: str,
        lead_public_id: str,
    ) -> list[ActivityView]:
        workspace = self._workspace(workspace_public_id)

        lead = self.leads.get_by_public_id(
            workspace_id=workspace.id,
            public_id=lead_public_id,
        )
        if lead is None:
            raise ActivityTargetError(
                f"Lead não encontrado nesta empresa: {lead_public_id}"
            )

        return [
            self._view(item)
            for item in self.activities.list_for_workspace(
                workspace.id
            )
            if item.lead_id == lead.id
        ]

    def list_for_opportunity(
        self,
        workspace_public_id: str,
        opportunity_public_id: str,
    ) -> list[ActivityView]:
        workspace = self._workspace(workspace_public_id)

        opportunity = self.opportunities.get_by_public_id(
            workspace_id=workspace.id,
            public_id=opportunity_public_id,
        )
        if opportunity is None:
            raise ActivityTargetError(
                "Oportunidade não encontrada nesta empresa: "
                f"{opportunity_public_id}"
            )

        return [
            self._view(item)
            for item in self.activities.list_for_workspace(
                workspace.id
            )
            if item.opportunity_id == opportunity.id
        ]

    def update(
        self,
        workspace_public_id: str,
        activity_public_id: str,
        payload: ActivityUpdate,
    ) -> ActivityView:
        workspace = self._workspace(workspace_public_id)

        activity = self.activities.get(
            workspace.id,
            activity_public_id,
        )
        if activity is None:
            raise ActivityNotFoundError(
                f"Atividade não encontrada: {activity_public_id}"
            )

        if activity.status != "pending":
            raise ActivityStateError(
                "Somente atividades pendentes podem ser alteradas."
            )

        before_view = self._view(activity)
        before_data = activity_snapshot(
            activity,
            lead_public_id=before_view.lead_public_id,
            opportunity_public_id=before_view.opportunity_public_id,
            owner_user_public_id=before_view.owner_user_public_id,
        )

        changes = payload.model_dump(exclude_unset=True)

        if "owner_user_public_id" in changes:
            activity.owner_membership_id = self._owner_membership_id(
                workspace_id=workspace.id,
                user_public_id=changes.pop("owner_user_public_id"),
            )

        if "due_at" in changes:
            changes["due_at"] = self._normalize_datetime(
                changes["due_at"]
            )

        for field_name in (
            "activity_type",
            "title",
            "description",
            "due_at",
        ):
            if field_name in changes:
                setattr(activity, field_name, changes[field_name])

        self.activities.save(activity)

        after_view = self._view(activity)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="activity",
            entity_public_id=activity.public_id,
            action="activity.updated",
            before_data=before_data,
            after_data=activity_snapshot(
                activity,
                lead_public_id=after_view.lead_public_id,
                opportunity_public_id=after_view.opportunity_public_id,
                owner_user_public_id=after_view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(activity)

        return self._view(activity)

    def complete(
        self,
        workspace_public_id: str,
        activity_public_id: str,
    ) -> ActivityView:
        view = self.get(
            workspace_public_id,
            activity_public_id,
        )

        if view.activity.status != "pending":
            raise ActivityStateError(
                "A atividade não está pendente."
            )

        before_data = activity_snapshot(
            view.activity,
            lead_public_id=view.lead_public_id,
            opportunity_public_id=view.opportunity_public_id,
            owner_user_public_id=view.owner_user_public_id,
        )

        view.activity.status = "completed"
        view.activity.completed_at = datetime.now(timezone.utc)
        view.activity.cancelled_at = None

        self.activities.save(view.activity)
        self.audit.record(
            workspace_id=view.activity.workspace_id,
            entity_type="activity",
            entity_public_id=view.activity.public_id,
            action="activity.completed",
            before_data=before_data,
            after_data=activity_snapshot(
                view.activity,
                lead_public_id=view.lead_public_id,
                opportunity_public_id=view.opportunity_public_id,
                owner_user_public_id=view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(view.activity)

        return self._view(view.activity)

    def cancel(
        self,
        workspace_public_id: str,
        activity_public_id: str,
    ) -> ActivityView:
        view = self.get(
            workspace_public_id,
            activity_public_id,
        )

        if view.activity.status != "pending":
            raise ActivityStateError(
                "A atividade não está pendente."
            )

        before_data = activity_snapshot(
            view.activity,
            lead_public_id=view.lead_public_id,
            opportunity_public_id=view.opportunity_public_id,
            owner_user_public_id=view.owner_user_public_id,
        )

        view.activity.status = "cancelled"
        view.activity.cancelled_at = datetime.now(timezone.utc)
        view.activity.completed_at = None

        self.activities.save(view.activity)
        self.audit.record(
            workspace_id=view.activity.workspace_id,
            entity_type="activity",
            entity_public_id=view.activity.public_id,
            action="activity.cancelled",
            before_data=before_data,
            after_data=activity_snapshot(
                view.activity,
                lead_public_id=view.lead_public_id,
                opportunity_public_id=view.opportunity_public_id,
                owner_user_public_id=view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(view.activity)

        return self._view(view.activity)

    def pending(
        self,
        workspace_public_id: str,
    ) -> list[ActivityView]:
        workspace = self._workspace(workspace_public_id)

        return [
            self._view(item)
            for item in self.activities.pending_for_workspace(
                workspace.id
            )
        ]
