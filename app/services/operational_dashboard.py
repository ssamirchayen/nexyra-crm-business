from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Lead,
    LeadCadenceEnrollment,
    User,
    WhatsAppMessage,
    WorkspaceMembership,
)
from app.repositories import WorkspaceRepository
from app.services.lead_recommendation import LeadRecommendationService
from app.services.lead_sla import LeadSlaService
from app.services.reports import ReportsService
from app.services.workspace import WorkspaceNotFoundError


class OperationalDashboardService:
    """Aggregate operational CRM signals without persisting derived data."""

    MAX_QUEUE_ITEMS = 5000
    MAX_RECOMMENDATIONS = 5000

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
    def _percentage(value: int, total: int) -> float:
        if total == 0:
            return 0.0
        return round((value / total) * 100, 1)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(f"Empresa não encontrada: {public_id}")
        return workspace

    def _owner_membership_id(
        self,
        *,
        workspace_id: int,
        owner_user_public_id: str | None,
    ) -> int | None:
        if owner_user_public_id is None:
            return None

        membership_id = self.db.scalar(
            select(WorkspaceMembership.id)
            .join(User, User.id == WorkspaceMembership.user_id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                User.public_id == owner_user_public_id,
            )
        )
        return int(membership_id) if membership_id is not None else None

    def overview(
        self,
        workspace_public_id: str,
        *,
        period_days: int = 30,
        owner_user_public_id: str | None = None,
    ) -> dict[str, object]:
        workspace = self._workspace(workspace_public_id)
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)

        # ReportsService validates an owner filter and provides the shared
        # commercial metrics/member options used by the management view.
        report = ReportsService(self.db).analytics(
            workspace_public_id,
            period_days=period_days,
            owner_user_public_id=owner_user_public_id,
        )

        owner_membership_id = self._owner_membership_id(
            workspace_id=workspace.id,
            owner_user_public_id=owner_user_public_id,
        )

        lead_statement = select(Lead).where(
            Lead.workspace_id == workspace.id,
            Lead.active.is_(True),
        )
        if owner_membership_id is not None:
            lead_statement = lead_statement.where(
                Lead.owner_membership_id == owner_membership_id
            )
        active_leads = list(self.db.scalars(lead_statement).all())
        active_lead_ids = {lead.id for lead in active_leads}

        sla = LeadSlaService(self.db).queue(
            workspace_public_id,
            owner_user_public_id=owner_user_public_id,
            limit=self.MAX_QUEUE_ITEMS,
        )
        recommendations = LeadRecommendationService(self.db).board(
            workspace_public_id,
            owner_user_public_id=owner_user_public_id,
            limit=self.MAX_RECOMMENDATIONS,
        )

        message_statement = select(WhatsAppMessage).where(
            WhatsAppMessage.workspace_id == workspace.id,
            WhatsAppMessage.created_at >= period_start,
        )
        if owner_membership_id is not None:
            if active_lead_ids:
                message_statement = message_statement.where(
                    WhatsAppMessage.lead_id.in_(active_lead_ids)
                )
            else:
                messages: list[WhatsAppMessage] = []
                message_statement = None
        if message_statement is not None:
            messages = list(self.db.scalars(message_statement).all())

        outbound_messages = [item for item in messages if item.direction == "outbound"]
        inbound_messages = [item for item in messages if item.direction == "inbound"]
        outbound_statuses = Counter(item.status for item in outbound_messages)
        delivered_or_read = (
            outbound_statuses.get("delivered", 0) + outbound_statuses.get("read", 0)
        )
        read_messages = outbound_statuses.get("read", 0)
        failed_messages = outbound_statuses.get("failed", 0)

        cadence_statement = select(LeadCadenceEnrollment).where(
            LeadCadenceEnrollment.workspace_id == workspace.id
        )
        if owner_membership_id is not None:
            if active_lead_ids:
                cadence_statement = cadence_statement.where(
                    LeadCadenceEnrollment.lead_id.in_(active_lead_ids)
                )
            else:
                enrollments: list[LeadCadenceEnrollment] = []
                cadence_statement = None
        if cadence_statement is not None:
            enrollments = list(self.db.scalars(cadence_statement).all())

        active_enrollments = [item for item in enrollments if item.status == "active"]
        active_cadence_leads = {item.lead_id for item in active_enrollments}
        completed_enrollments = [
            item
            for item in enrollments
            if item.status == "completed"
            and self._in_period(item.completed_at, period_start, now)
        ]
        cancelled_enrollments = [
            item
            for item in enrollments
            if item.status == "cancelled"
            and self._in_period(item.cancelled_at, period_start, now)
        ]

        unassigned_leads = sum(
            lead.owner_membership_id is None for lead in active_leads
        )
        high_priority_leads = sum(
            lead.priority in {"alta", "urgente"} for lead in active_leads
        )

        sla_metrics = sla.metrics
        recommendation_metrics = recommendations["metrics"]

        bottleneck_candidates = [
            (
                "sla_breached",
                "SLA de primeiro contato estourado",
                sla_metrics.sla_breached,
                "critical",
                "/service-queue",
            ),
            (
                "overdue_followups",
                "Follow-ups vencidos",
                sla_metrics.overdue_followups,
                "critical",
                "/service-queue",
            ),
            (
                "awaiting_whatsapp",
                "Conversas aguardando resposta",
                int(recommendation_metrics["awaiting_reply"]),
                "warning",
                "/inbox",
            ),
            (
                "opportunities_at_risk",
                "Oportunidades em risco",
                int(recommendation_metrics["opportunities_at_risk"]),
                "warning",
                "/recommendations",
            ),
            (
                "unassigned",
                "Leads sem responsável",
                unassigned_leads,
                "warning",
                "/leads",
            ),
            (
                "whatsapp_failed",
                "Falhas de envio no WhatsApp",
                failed_messages,
                "critical",
                "/inbox",
            ),
        ]
        severity_weight = {"critical": 2, "warning": 1}
        bottlenecks = [
            {
                "code": code,
                "title": title,
                "count": count,
                "severity": severity,
                "route": route,
            }
            for code, title, count, severity, route in sorted(
                bottleneck_candidates,
                key=lambda item: (-severity_weight[item[3]], -item[2], item[1]),
            )
            if count > 0
        ]

        return {
            "workspace_public_id": workspace.public_id,
            "workspace_name": workspace.name,
            "generated_at": now,
            "period_days": period_days,
            "period_start": period_start,
            "period_end": now,
            "owner_user_public_id_filter": owner_user_public_id,
            "available_members": report["available_members"],
            "active_leads": len(active_leads),
            "leads_created": int(report["total_leads"]),
            "high_priority_leads": high_priority_leads,
            "unassigned_leads": unassigned_leads,
            "open_opportunities": int(report["open_opportunities"]),
            "open_pipeline_value": report["open_pipeline_value"],
            "conversion_rate": float(report["conversion_rate"]),
            "won_value": report["won_value"],
            "pending_activities": int(report["pending_activities"]),
            "overdue_activities": int(report["overdue_activities"]),
            "sla": {
                "total_attention": sla_metrics.total_attention,
                "awaiting_first_contact": sla_metrics.awaiting_first_contact,
                "warning": sla_metrics.sla_warning,
                "breached": sla_metrics.sla_breached,
                "overdue_followups": sla_metrics.overdue_followups,
                "due_soon_followups": sla_metrics.due_soon_followups,
                "stale_leads": sla_metrics.stale_leads,
                "attention_share_percent": self._percentage(
                    sla_metrics.total_attention,
                    len(active_leads),
                ),
            },
            "recommendations": {
                "total": int(recommendation_metrics["total_leads"]),
                "critical": int(recommendation_metrics["critical"]),
                "high": int(recommendation_metrics["high"]),
                "awaiting_reply": int(recommendation_metrics["awaiting_reply"]),
                "opportunities_at_risk": int(
                    recommendation_metrics["opportunities_at_risk"]
                ),
            },
            "whatsapp": {
                "inbound": len(inbound_messages),
                "outbound": len(outbound_messages),
                "sent": outbound_statuses.get("sent", 0),
                "delivered": outbound_statuses.get("delivered", 0),
                "read": read_messages,
                "failed": failed_messages,
                "delivery_rate": self._percentage(
                    delivered_or_read,
                    len(outbound_messages),
                ),
                "read_rate": self._percentage(
                    read_messages,
                    len(outbound_messages),
                ),
            },
            "cadences": {
                "active_enrollments": len(active_enrollments),
                "active_leads": len(active_cadence_leads),
                "completed_in_period": len(completed_enrollments),
                "cancelled_in_period": len(cancelled_enrollments),
                "coverage_percent": self._percentage(
                    len(active_cadence_leads),
                    len(active_leads),
                ),
            },
            "bottlenecks": bottlenecks,
            "pipeline_stages": report["pipeline_stages"],
            "member_performance": report["member_performance"],
        }
