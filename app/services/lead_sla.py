from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Lead,
    User,
    WhatsAppMessage,
    Workspace,
    WorkspaceMembership,
)
from app.repositories import (
    LeadSlaConfigRepository,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.schemas.lead_sla import LeadSlaConfigUpdate
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError

CONTACT_ACTIVITY_TYPES = frozenset(
    {"call", "whatsapp", "email", "meeting", "follow_up"}
)
PRIORITY_SCORE = {
    "baixa": 0,
    "media": 80,
    "alta": 180,
    "urgente": 300,
}


class LeadSlaConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LeadSlaQueueItem:
    lead: Lead
    owner_user_public_id: str | None
    owner_name: str | None
    age_minutes: int
    first_contact_at: datetime | None
    first_response_minutes: int | None
    sla_due_at: datetime
    sla_state: str
    last_contact_at: datetime | None
    pending_followups: int
    overdue_followups: int
    next_followup_due_at: datetime | None
    stale: bool
    score: int
    reasons: list[str]


@dataclass(frozen=True)
class LeadSlaQueueMetrics:
    total_attention: int
    awaiting_first_contact: int
    sla_warning: int
    sla_breached: int
    overdue_followups: int
    due_soon_followups: int
    stale_leads: int
    unassigned: int


@dataclass(frozen=True)
class LeadSlaQueue:
    config: LeadSlaConfigUpdate
    metrics: LeadSlaQueueMetrics
    items: list[LeadSlaQueueItem]


class LeadSlaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.configs = LeadSlaConfigRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str) -> Workspace:
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(f"Empresa não encontrada: {public_id}")
        return workspace

    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _default_config() -> LeadSlaConfigUpdate:
        return LeadSlaConfigUpdate()

    @staticmethod
    def _config_payload(model) -> LeadSlaConfigUpdate:
        if model is None:
            return LeadSlaService._default_config()
        return LeadSlaConfigUpdate(
            enabled=model.enabled,
            first_response_minutes=model.first_response_minutes,
            warning_before_minutes=model.warning_before_minutes,
            follow_up_due_hours=model.follow_up_due_hours,
            stale_lead_hours=model.stale_lead_hours,
        )

    def get_config(self, workspace_public_id: str) -> LeadSlaConfigUpdate:
        workspace = self._workspace(workspace_public_id)
        return self._config_payload(
            self.configs.get_by_workspace_id(workspace.id)
        )

    def save_config(
        self,
        workspace_public_id: str,
        payload: LeadSlaConfigUpdate,
    ) -> LeadSlaConfigUpdate:
        workspace = self._workspace(workspace_public_id)
        config = self.configs.get_by_workspace_id(workspace.id)
        values = payload.model_dump()

        if config is None:
            config = self.configs.create(workspace_id=workspace.id, **values)
        else:
            for key, value in values.items():
                setattr(config, key, value)
            self.configs.save(config)

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead_sla",
            entity_public_id=workspace.public_id,
            action="lead_sla.config_updated",
            after_data=values,
        )
        self.db.commit()
        return self._config_payload(config)

    def _owner_membership_id(
        self,
        *,
        workspace_id: int,
        user_public_id: str,
    ) -> int:
        user = self.users.get_by_public_id(user_public_id)
        if user is None:
            raise LeadSlaConfigError(
                f"Responsável não encontrado: {user_public_id}"
            )
        membership = self.memberships.get(
            workspace_id=workspace_id,
            user_id=user.id,
        )
        if membership is None or not membership.active:
            raise LeadSlaConfigError(
                "O responsável não possui acesso ativo a esta empresa."
            )
        return membership.id

    def _lead_rows(
        self,
        *,
        workspace_id: int,
    ) -> list[tuple[Lead, str | None, str | None]]:
        statement = (
            select(Lead, User.public_id, User.name)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == Lead.owner_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(
                Lead.workspace_id == workspace_id,
                Lead.active.is_(True),
            )
            .order_by(Lead.id.asc())
        )
        return [tuple(row) for row in self.db.execute(statement).all()]

    def _contact_maps(
        self,
        *,
        workspace_id: int,
    ) -> tuple[dict[int, datetime], dict[int, datetime]]:
        contacts: dict[int, list[datetime]] = {}

        activities = self.db.scalars(
            select(Activity).where(
                Activity.workspace_id == workspace_id,
                Activity.lead_id.is_not(None),
                Activity.status == "completed",
                Activity.completed_at.is_not(None),
                Activity.activity_type.in_(CONTACT_ACTIVITY_TYPES),
            )
        ).all()
        for activity in activities:
            assert activity.lead_id is not None
            completed_at = self._aware(activity.completed_at)
            if completed_at is not None:
                contacts.setdefault(activity.lead_id, []).append(completed_at)

        messages = self.db.scalars(
            select(WhatsAppMessage).where(
                WhatsAppMessage.workspace_id == workspace_id,
                WhatsAppMessage.lead_id.is_not(None),
                WhatsAppMessage.direction == "outbound",
                WhatsAppMessage.status != "failed",
            )
        ).all()
        for message in messages:
            assert message.lead_id is not None
            contact_at = self._aware(
                message.provider_timestamp or message.created_at
            )
            if contact_at is not None:
                contacts.setdefault(message.lead_id, []).append(contact_at)

        first: dict[int, datetime] = {}
        last: dict[int, datetime] = {}
        for lead_id, values in contacts.items():
            first[lead_id] = min(values)
            last[lead_id] = max(values)
        return first, last

    def _followup_maps(
        self,
        *,
        workspace_id: int,
        now: datetime,
    ) -> tuple[dict[int, int], dict[int, int], dict[int, datetime]]:
        pending: dict[int, int] = {}
        overdue: dict[int, int] = {}
        next_due: dict[int, datetime] = {}

        activities = self.db.scalars(
            select(Activity).where(
                Activity.workspace_id == workspace_id,
                Activity.lead_id.is_not(None),
                Activity.status == "pending",
                Activity.due_at.is_not(None),
            )
        ).all()
        for activity in activities:
            assert activity.lead_id is not None
            due_at = self._aware(activity.due_at)
            if due_at is None:
                continue
            lead_id = activity.lead_id
            pending[lead_id] = pending.get(lead_id, 0) + 1
            if due_at < now:
                overdue[lead_id] = overdue.get(lead_id, 0) + 1
            current = next_due.get(lead_id)
            if current is None or due_at < current:
                next_due[lead_id] = due_at

        return pending, overdue, next_due

    @staticmethod
    def _minutes(delta: timedelta) -> int:
        return max(0, int(delta.total_seconds() // 60))

    def queue(
        self,
        workspace_public_id: str,
        *,
        owner_user_public_id: str | None = None,
        only_unassigned: bool = False,
        limit: int = 100,
        now: datetime | None = None,
    ) -> LeadSlaQueue:
        workspace = self._workspace(workspace_public_id)
        config = self._config_payload(
            self.configs.get_by_workspace_id(workspace.id)
        )
        current = self._aware(now) or datetime.now(timezone.utc)
        owner_membership_id = None
        if owner_user_public_id:
            owner_membership_id = self._owner_membership_id(
                workspace_id=workspace.id,
                user_public_id=owner_user_public_id,
            )

        first_contacts, last_contacts = self._contact_maps(
            workspace_id=workspace.id
        )
        pending, overdue, next_due = self._followup_maps(
            workspace_id=workspace.id,
            now=current,
        )

        items: list[LeadSlaQueueItem] = []
        due_soon_cutoff = current + timedelta(hours=config.follow_up_due_hours)

        for lead, owner_public_id, owner_name in self._lead_rows(
            workspace_id=workspace.id
        ):
            if (
                owner_membership_id is not None
                and lead.owner_membership_id != owner_membership_id
            ):
                continue
            if only_unassigned and lead.owner_membership_id is not None:
                continue

            created_at = self._aware(lead.created_at) or current
            age_minutes = self._minutes(current - created_at)
            sla_due_at = created_at + timedelta(
                minutes=config.first_response_minutes
            )
            warning_at = sla_due_at - timedelta(
                minutes=config.warning_before_minutes
            )
            first_contact = first_contacts.get(lead.id)
            last_contact = last_contacts.get(lead.id)
            pending_count = pending.get(lead.id, 0)
            overdue_count = overdue.get(lead.id, 0)
            next_due_at = next_due.get(lead.id)
            stale = bool(
                last_contact
                and current - last_contact
                >= timedelta(hours=config.stale_lead_hours)
            )
            due_soon = bool(
                next_due_at
                and current <= next_due_at <= due_soon_cutoff
            )

            reasons: list[str] = []
            score = PRIORITY_SCORE.get(lead.priority, 0)

            if first_contact is None:
                if current >= sla_due_at:
                    sla_state = "breached"
                    reasons.append("first_response_breached")
                    score += 1000 + min(age_minutes, 720)
                elif current >= warning_at:
                    sla_state = "warning"
                    reasons.append("first_response_warning")
                    score += 650
                else:
                    sla_state = "within_sla"
                    reasons.append("awaiting_first_contact")
                    score += 350
                first_response_minutes = None
            else:
                sla_state = "contacted"
                first_response_minutes = self._minutes(
                    first_contact - created_at
                )

            if overdue_count:
                reasons.append("overdue_followup")
                score += 850 + (overdue_count * 100)
            elif due_soon:
                reasons.append("followup_due_soon")
                score += 300

            if stale:
                reasons.append("stale_lead")
                score += 450

            if lead.owner_membership_id is None:
                reasons.append("unassigned")
                score += 120

            needs_attention = bool(
                first_contact is None
                or overdue_count
                or due_soon
                or stale
            )
            if not config.enabled or not needs_attention:
                continue

            items.append(
                LeadSlaQueueItem(
                    lead=lead,
                    owner_user_public_id=owner_public_id,
                    owner_name=owner_name,
                    age_minutes=age_minutes,
                    first_contact_at=first_contact,
                    first_response_minutes=first_response_minutes,
                    sla_due_at=sla_due_at,
                    sla_state=sla_state,
                    last_contact_at=last_contact,
                    pending_followups=pending_count,
                    overdue_followups=overdue_count,
                    next_followup_due_at=next_due_at,
                    stale=stale,
                    score=score,
                    reasons=reasons,
                )
            )

        items.sort(
            key=lambda item: (
                -item.score,
                self._aware(item.lead.created_at) or current,
                item.lead.id,
            )
        )
        items = items[:limit]

        metrics = LeadSlaQueueMetrics(
            total_attention=len(items),
            awaiting_first_contact=sum(
                item.first_contact_at is None for item in items
            ),
            sla_warning=sum(item.sla_state == "warning" for item in items),
            sla_breached=sum(item.sla_state == "breached" for item in items),
            overdue_followups=sum(
                item.overdue_followups > 0 for item in items
            ),
            due_soon_followups=sum(
                "followup_due_soon" in item.reasons for item in items
            ),
            stale_leads=sum(item.stale for item in items),
            unassigned=sum(
                item.lead.owner_membership_id is None for item in items
            ),
        )
        return LeadSlaQueue(config=config, metrics=metrics, items=items)
