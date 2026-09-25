from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Lead,
    LeadCadence,
    LeadCadenceEnrollment,
    LeadCadenceStep,
    WhatsAppMessage,
)
from app.repositories import ActivityRepository, WorkspaceRepository
from app.schemas import LeadCadenceCreate, LeadCadenceStepInput, LeadCadenceUpdate
from app.services.audit import AuditService
from app.services.communication_consent import (
    CommunicationBlockedError,
    CommunicationConsentService,
)
from app.services.workspace import WorkspaceNotFoundError


class LeadCadenceNotFoundError(ValueError):
    pass


class LeadCadenceEnrollmentError(ValueError):
    pass


@dataclass(frozen=True)
class CadenceView:
    cadence: LeadCadence
    steps: list[LeadCadenceStep]
    active_enrollments: int


@dataclass(frozen=True)
class EnrollmentView:
    enrollment: LeadCadenceEnrollment
    lead: Lead
    cadence: LeadCadence
    total_steps: int


@dataclass(frozen=True)
class ProcessResult:
    processed: int
    activities_created: int
    completed: int
    cancelled: int


class LeadCadenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.activities = ActivityRepository(db)
        self.audit = AuditService(db)
        self.communication = CommunicationConsentService(db)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(f"Empresa não encontrada: {public_id}")
        return workspace

    def _cadence(self, workspace_id: int, public_id: str) -> LeadCadence:
        cadence = self.db.scalar(
            select(LeadCadence).where(
                LeadCadence.workspace_id == workspace_id,
                LeadCadence.public_id == public_id,
            )
        )
        if cadence is None:
            raise LeadCadenceNotFoundError(f"Cadência não encontrada: {public_id}")
        return cadence

    def _steps(self, cadence_id: int) -> list[LeadCadenceStep]:
        return list(
            self.db.scalars(
                select(LeadCadenceStep)
                .where(LeadCadenceStep.cadence_id == cadence_id)
                .order_by(LeadCadenceStep.position.asc())
            ).all()
        )

    def _view(self, cadence: LeadCadence) -> CadenceView:
        active = int(
            self.db.scalar(
                select(func.count(LeadCadenceEnrollment.id)).where(
                    LeadCadenceEnrollment.cadence_id == cadence.id,
                    LeadCadenceEnrollment.status == "active",
                )
            )
            or 0
        )
        return CadenceView(cadence, self._steps(cadence.id), active)

    def list(self, workspace_public_id: str) -> list[CadenceView]:
        workspace = self._workspace(workspace_public_id)
        rows = self.db.scalars(
            select(LeadCadence)
            .where(LeadCadence.workspace_id == workspace.id)
            .order_by(LeadCadence.active.desc(), LeadCadence.id.desc())
        ).all()
        return [self._view(item) for item in rows]

    def create(self, workspace_public_id: str, payload: LeadCadenceCreate) -> CadenceView:
        workspace = self._workspace(workspace_public_id)
        cadence = LeadCadence(
            workspace_id=workspace.id,
            name=payload.name.strip(),
            description=payload.description,
            active=payload.active,
            stop_on_reply=payload.stop_on_reply,
        )
        self.db.add(cadence)
        self.db.flush()
        self._replace_steps(cadence.id, payload.steps)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead_cadence",
            entity_public_id=cadence.public_id,
            action="lead_cadence.created",
            after_data={"name": cadence.name, "steps": len(payload.steps)},
        )
        self.db.commit()
        self.db.refresh(cadence)
        return self._view(cadence)

    def update(
        self,
        workspace_public_id: str,
        cadence_public_id: str,
        payload: LeadCadenceUpdate,
    ) -> CadenceView:
        workspace = self._workspace(workspace_public_id)
        cadence = self._cadence(workspace.id, cadence_public_id)
        before = {"name": cadence.name, "active": cadence.active}
        values = payload.model_dump(exclude_unset=True, exclude={"steps"})
        for key, value in values.items():
            if key == "name" and isinstance(value, str):
                value = value.strip()
            setattr(cadence, key, value)
        if payload.steps is not None:
            active_count = int(
                self.db.scalar(
                    select(func.count(LeadCadenceEnrollment.id)).where(
                        LeadCadenceEnrollment.cadence_id == cadence.id,
                        LeadCadenceEnrollment.status == "active",
                    )
                )
                or 0
            )
            if active_count:
                raise LeadCadenceEnrollmentError(
                    "Não é possível alterar etapas enquanto houver leads ativos na cadência."
                )
            self._replace_steps(cadence.id, payload.steps)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead_cadence",
            entity_public_id=cadence.public_id,
            action="lead_cadence.updated",
            before_data=before,
            after_data={"name": cadence.name, "active": cadence.active},
        )
        self.db.commit()
        self.db.refresh(cadence)
        return self._view(cadence)

    def _replace_steps(self, cadence_id: int, steps: list[LeadCadenceStepInput]) -> None:
        existing = self._steps(cadence_id)
        for item in existing:
            self.db.delete(item)
        self.db.flush()
        for position, item in enumerate(steps, start=1):
            self.db.add(
                LeadCadenceStep(
                    cadence_id=cadence_id,
                    position=position,
                    delay_minutes=item.delay_minutes,
                    action_type=item.action_type,
                    title=item.title.strip(),
                    message_template=item.message_template,
                )
            )
        self.db.flush()

    def preview(
        self,
        workspace_public_id: str,
        cadence_public_id: str,
        *,
        start_at: datetime | None = None,
    ) -> list[tuple[LeadCadenceStep, datetime]]:
        workspace = self._workspace(workspace_public_id)
        cadence = self._cadence(workspace.id, cadence_public_id)
        cursor = self._aware(start_at or datetime.now(timezone.utc))
        output: list[tuple[LeadCadenceStep, datetime]] = []
        for step in self._steps(cadence.id):
            cursor += timedelta(minutes=step.delay_minutes)
            output.append((step, cursor))
        return output

    def enroll(
        self,
        workspace_public_id: str,
        *,
        lead_public_id: str,
        cadence_public_id: str,
    ) -> EnrollmentView:
        workspace = self._workspace(workspace_public_id)
        cadence = self._cadence(workspace.id, cadence_public_id)
        if not cadence.active:
            raise LeadCadenceEnrollmentError("A cadência está inativa.")
        lead = self.db.scalar(
            select(Lead).where(
                Lead.workspace_id == workspace.id,
                Lead.public_id == lead_public_id,
                Lead.active.is_(True),
            )
        )
        if lead is None:
            raise LeadCadenceEnrollmentError("Lead ativo não encontrado.")
        duplicate = self.db.scalar(
            select(LeadCadenceEnrollment).where(
                LeadCadenceEnrollment.workspace_id == workspace.id,
                LeadCadenceEnrollment.lead_id == lead.id,
                LeadCadenceEnrollment.status == "active",
            )
        )
        if duplicate is not None:
            raise LeadCadenceEnrollmentError("O lead já participa de uma cadência ativa.")
        steps = self._steps(cadence.id)
        if not steps:
            raise LeadCadenceEnrollmentError("A cadência não possui etapas.")
        for channel in self._cadence_channels(steps):
            try:
                self.communication.assert_allowed_for_lead(lead, channel)
            except CommunicationBlockedError as exc:
                raise LeadCadenceEnrollmentError(str(exc)) from exc
        now = datetime.now(timezone.utc)
        enrollment = LeadCadenceEnrollment(
            workspace_id=workspace.id,
            cadence_id=cadence.id,
            lead_id=lead.id,
            status="active",
            current_step=0,
            next_run_at=now + timedelta(minutes=steps[0].delay_minutes),
        )
        self.db.add(enrollment)
        self.db.flush()
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead_cadence_enrollment",
            entity_public_id=enrollment.public_id,
            action="lead_cadence.enrolled",
            metadata={"lead_public_id": lead.public_id, "cadence_public_id": cadence.public_id},
        )
        self.db.commit()
        self.db.refresh(enrollment)
        return EnrollmentView(enrollment, lead, cadence, len(steps))

    def list_enrollments(self, workspace_public_id: str) -> list[EnrollmentView]:
        workspace = self._workspace(workspace_public_id)
        rows = self.db.execute(
            select(LeadCadenceEnrollment, Lead, LeadCadence)
            .join(Lead, Lead.id == LeadCadenceEnrollment.lead_id)
            .join(LeadCadence, LeadCadence.id == LeadCadenceEnrollment.cadence_id)
            .where(LeadCadenceEnrollment.workspace_id == workspace.id)
            .order_by(LeadCadenceEnrollment.status.asc(), LeadCadenceEnrollment.id.desc())
            .limit(250)
        ).all()
        return [
            EnrollmentView(enrollment, lead, cadence, len(self._steps(cadence.id)))
            for enrollment, lead, cadence in rows
        ]

    def cancel(self, workspace_public_id: str, enrollment_public_id: str) -> EnrollmentView:
        workspace = self._workspace(workspace_public_id)
        enrollment = self.db.scalar(
            select(LeadCadenceEnrollment).where(
                LeadCadenceEnrollment.workspace_id == workspace.id,
                LeadCadenceEnrollment.public_id == enrollment_public_id,
            )
        )
        if enrollment is None:
            raise LeadCadenceEnrollmentError("Inscrição de cadência não encontrada.")
        if enrollment.status == "active":
            enrollment.status = "cancelled"
            enrollment.cancelled_at = datetime.now(timezone.utc)
            enrollment.next_run_at = None
            self.audit.record(
                workspace_id=workspace.id,
                entity_type="lead_cadence_enrollment",
                entity_public_id=enrollment.public_id,
                action="lead_cadence.cancelled",
            )
            self.db.commit()
        lead = self.db.get(Lead, enrollment.lead_id)
        cadence = self.db.get(LeadCadence, enrollment.cadence_id)
        assert lead is not None and cadence is not None
        return EnrollmentView(enrollment, lead, cadence, len(self._steps(cadence.id)))

    def process_due(self, workspace_public_id: str, *, limit: int = 100) -> ProcessResult:
        workspace = self._workspace(workspace_public_id)
        now = datetime.now(timezone.utc)
        enrollments = list(
            self.db.scalars(
                select(LeadCadenceEnrollment)
                .where(
                    LeadCadenceEnrollment.workspace_id == workspace.id,
                    LeadCadenceEnrollment.status == "active",
                    LeadCadenceEnrollment.next_run_at.is_not(None),
                    LeadCadenceEnrollment.next_run_at <= now,
                )
                .order_by(LeadCadenceEnrollment.next_run_at.asc())
                .limit(limit)
            ).all()
        )
        processed = created = completed = cancelled = 0
        for enrollment in enrollments:
            cadence = self.db.get(LeadCadence, enrollment.cadence_id)
            lead = self.db.get(Lead, enrollment.lead_id)
            if cadence is None or lead is None or not cadence.active or not lead.active:
                enrollment.status = "cancelled"
                enrollment.cancelled_at = now
                enrollment.next_run_at = None
                cancelled += 1
                processed += 1
                continue
            if cadence.stop_on_reply and self._has_reply_since(enrollment):
                enrollment.status = "cancelled"
                enrollment.cancelled_at = now
                enrollment.next_run_at = None
                cancelled += 1
                processed += 1
                continue
            steps = self._steps(cadence.id)
            if enrollment.current_step >= len(steps):
                enrollment.status = "completed"
                enrollment.completed_at = now
                enrollment.next_run_at = None
                completed += 1
                processed += 1
                continue
            step = steps[enrollment.current_step]
            communication_channel = self._step_channel(step.action_type)
            if communication_channel is not None:
                try:
                    self.communication.assert_allowed_for_lead(
                        lead,
                        communication_channel,
                    )
                except CommunicationBlockedError as exc:
                    processed += 1
                    stop_cadence = self.communication.should_stop_cadence(
                        workspace.id
                    )
                    self.audit.record(
                        workspace_id=workspace.id,
                        entity_type="lead_cadence_enrollment",
                        entity_public_id=enrollment.public_id,
                        action=(
                            "lead_cadence.blocked_by_consent"
                            if stop_cadence
                            else "lead_cadence.step_skipped_by_consent"
                        ),
                        metadata={
                            "lead_public_id": lead.public_id,
                            "cadence_public_id": cadence.public_id,
                            "step": step.position,
                            "channel": communication_channel,
                            "reason": str(exc),
                        },
                    )
                    if stop_cadence:
                        enrollment.status = "cancelled"
                        enrollment.cancelled_at = now
                        enrollment.next_run_at = None
                        cancelled += 1
                        continue
                    enrollment.current_step += 1
                    if enrollment.current_step >= len(steps):
                        enrollment.status = "completed"
                        enrollment.completed_at = now
                        enrollment.next_run_at = None
                        completed += 1
                    else:
                        next_step = steps[enrollment.current_step]
                        enrollment.next_run_at = now + timedelta(
                            minutes=next_step.delay_minutes
                        )
                    continue
            self.activities.create(
                workspace_id=workspace.id,
                lead_id=lead.id,
                opportunity_id=None,
                owner_membership_id=lead.owner_membership_id,
                activity_type=step.action_type,
                title=self._render(step.title, lead),
                description=self._render(step.message_template, lead),
                status="pending",
                due_at=now,
            )
            created += 1
            processed += 1
            enrollment.current_step += 1
            if enrollment.current_step >= len(steps):
                enrollment.status = "completed"
                enrollment.completed_at = now
                enrollment.next_run_at = None
                completed += 1
            else:
                next_step = steps[enrollment.current_step]
                enrollment.next_run_at = now + timedelta(minutes=next_step.delay_minutes)
            self.audit.record(
                workspace_id=workspace.id,
                entity_type="lead_cadence_enrollment",
                entity_public_id=enrollment.public_id,
                action="lead_cadence.step_executed",
                metadata={
                    "lead_public_id": lead.public_id,
                    "cadence_public_id": cadence.public_id,
                    "step": step.position,
                    "action_type": step.action_type,
                },
            )
        self.db.commit()
        return ProcessResult(processed, created, completed, cancelled)

    def _has_reply_since(self, enrollment: LeadCadenceEnrollment) -> bool:
        started = self._aware(enrollment.started_at)
        count = self.db.scalar(
            select(func.count(WhatsAppMessage.id)).where(
                WhatsAppMessage.lead_id == enrollment.lead_id,
                WhatsAppMessage.direction == "inbound",
                WhatsAppMessage.created_at >= started,
            )
        )
        return bool(count)

    @staticmethod
    def _step_channel(action_type: str) -> str | None:
        return {
            "whatsapp": "whatsapp",
            "email": "email",
            "call": "phone",
        }.get(action_type)

    @classmethod
    def _cadence_channels(
        cls,
        steps: list[LeadCadenceStep],
    ) -> set[str]:
        return {
            channel
            for step in steps
            if (channel := cls._step_channel(step.action_type)) is not None
        }

    @staticmethod
    def _render(template: str | None, lead: Lead) -> str | None:
        if template is None:
            return None
        return (
            template.replace("{{lead_name}}", lead.name)
            .replace("{{interest}}", lead.interest or "")
            .replace("{{phone}}", lead.phone or "")
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
