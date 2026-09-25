from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Lead,
    LeadCadenceEnrollment,
    Opportunity,
    User,
    WhatsAppMessage,
    WorkspaceMembership,
)
from app.repositories import WorkspaceRepository
from app.services.communication_consent import CommunicationConsentService
from app.services.lead_sla import LeadSlaService
from app.services.workspace import WorkspaceNotFoundError

CONTACT_TYPES = frozenset({"call", "whatsapp", "email", "meeting", "follow_up"})
PRIORITY_POINTS = {"baixa": 0, "media": 8, "alta": 18, "urgente": 28}


@dataclass(frozen=True, slots=True)
class Candidate:
    weight: int
    action: str
    title: str
    code: str
    reason: str


class LeadRecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.consent = CommunicationConsentService(db)

    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(f"Empresa não encontrada: {public_id}")
        return workspace

    def _leads(self, workspace_id: int):
        statement = (
            select(Lead, User.public_id, User.name)
            .outerjoin(
                WorkspaceMembership,
                WorkspaceMembership.id == Lead.owner_membership_id,
            )
            .outerjoin(User, User.id == WorkspaceMembership.user_id)
            .where(Lead.workspace_id == workspace_id, Lead.active.is_(True))
            .order_by(Lead.id.asc())
        )
        return [tuple(row) for row in self.db.execute(statement).all()]

    def _activity_maps(self, workspace_id: int):
        last_contact: dict[int, datetime] = {}
        contact_hours: Counter[int] = Counter()
        rows = self.db.scalars(
            select(Activity).where(Activity.workspace_id == workspace_id)
        ).all()
        for item in rows:
            if item.lead_id is None:
                continue
            if item.status == "completed" and item.activity_type in CONTACT_TYPES:
                completed = self._aware(item.completed_at or item.updated_at)
                if completed is not None:
                    current = last_contact.get(item.lead_id)
                    if current is None or completed > current:
                        last_contact[item.lead_id] = completed
                    contact_hours[completed.hour] += 1
        return last_contact, contact_hours

    def _whatsapp_map(self, workspace_id: int):
        latest: dict[int, WhatsAppMessage] = {}
        rows = self.db.scalars(
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.workspace_id == workspace_id,
                WhatsAppMessage.lead_id.is_not(None),
            )
            .order_by(WhatsAppMessage.created_at.asc(), WhatsAppMessage.id.asc())
        ).all()
        for item in rows:
            if item.lead_id is not None:
                latest[item.lead_id] = item
        return latest

    def _active_cadences(self, workspace_id: int) -> set[int]:
        return set(
            self.db.scalars(
                select(LeadCadenceEnrollment.lead_id).where(
                    LeadCadenceEnrollment.workspace_id == workspace_id,
                    LeadCadenceEnrollment.status == "active",
                )
            ).all()
        )

    def _open_opportunities(self, workspace_id: int) -> dict[int, Opportunity]:
        result: dict[int, Opportunity] = {}
        rows = self.db.scalars(
            select(Opportunity)
            .where(
                Opportunity.workspace_id == workspace_id,
                Opportunity.status == "open",
            )
            .order_by(Opportunity.updated_at.asc(), Opportunity.id.asc())
        ).all()
        for item in rows:
            result[item.lead_id] = item
        return result

    @staticmethod
    def _contact_window(hours: Counter[int]) -> str | None:
        if sum(hours.values()) < 3:
            return None
        hour, _ = max(hours.items(), key=lambda entry: (entry[1], -entry[0]))
        end = (hour + 2) % 24
        return f"{hour:02d}:00–{end:02d}:00"

    def _channel(self, lead: Lead, *, waiting_whatsapp: bool) -> str:
        if waiting_whatsapp and lead.phone:
            eligibility = self.consent.eligibility_for_lead(lead, "whatsapp")
            if eligibility.allowed:
                return "whatsapp"
        if lead.phone:
            whatsapp = self.consent.eligibility_for_lead(lead, "whatsapp")
            if whatsapp.allowed:
                return "whatsapp"
            phone = self.consent.eligibility_for_lead(lead, "phone")
            if phone.allowed:
                return "phone"
        if lead.email:
            email = self.consent.eligibility_for_lead(lead, "email")
            if email.allowed:
                return "email"
        return "manual"

    @staticmethod
    def _urgency(score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 35:
            return "medium"
        return "low"

    def board(
        self,
        workspace_public_id: str,
        *,
        owner_user_public_id: str | None = None,
        urgency: str | None = None,
        action: str | None = None,
        limit: int = 150,
    ) -> dict[str, object]:
        workspace = self._workspace(workspace_public_id)
        now = datetime.now(timezone.utc)
        sla_queue = LeadSlaService(self.db).queue(
            workspace_public_id,
            limit=500,
        )
        sla_by_lead = {item.lead.id: item for item in sla_queue.items}
        last_contact, contact_hours = self._activity_maps(workspace.id)
        whatsapp_by_lead = self._whatsapp_map(workspace.id)
        active_cadences = self._active_cadences(workspace.id)
        opportunities = self._open_opportunities(workspace.id)
        contact_window = self._contact_window(contact_hours)

        items: list[dict[str, object]] = []
        for lead, owner_public_id, owner_name in self._leads(workspace.id):
            if owner_user_public_id and owner_public_id != owner_user_public_id:
                continue

            sla = sla_by_lead.get(lead.id)
            latest_message = whatsapp_by_lead.get(lead.id)
            latest_message_at = self._aware(
                latest_message.provider_timestamp or latest_message.created_at
            ) if latest_message is not None else None
            waiting_whatsapp = bool(
                latest_message is not None and latest_message.direction == "inbound"
            )
            active_cadence = lead.id in active_cadences
            opportunity = opportunities.get(lead.id)
            opportunity_updated = (
                self._aware(opportunity.updated_at) if opportunity else None
            )
            opportunity_at_risk = bool(
                opportunity is not None
                and opportunity_updated is not None
                and opportunity_updated <= now - timedelta(days=3)
            )

            candidates: list[Candidate] = []
            score = PRIORITY_POINTS.get(lead.priority, 8)
            reasons: list[str] = []
            reason_codes: list[str] = []

            def add(
                candidate: Candidate,
                points: int,
                *,
                _candidates: list[Candidate] = candidates,
                _reasons: list[str] = reasons,
                _reason_codes: list[str] = reason_codes,
            ) -> None:
                nonlocal score
                _candidates.append(candidate)
                score += points
                _reasons.append(candidate.reason)
                _reason_codes.append(candidate.code)

            if owner_public_id is None:
                add(
                    Candidate(
                        110,
                        "assign_owner",
                        "Atribuir responsável",
                        "unassigned",
                        "Lead ativo ainda está sem responsável.",
                    ),
                    28,
                )
            if waiting_whatsapp:
                add(
                    Candidate(
                        105,
                        "reply_whatsapp",
                        "Responder WhatsApp",
                        "awaiting_whatsapp_reply",
                        "A última mensagem do lead no WhatsApp ainda aguarda resposta.",
                    ),
                    45,
                )
            if sla is not None:
                if sla.sla_state == "breached":
                    add(
                        Candidate(
                            100,
                            "first_contact",
                            "Realizar primeiro contato",
                            "first_response_breached",
                            "O SLA de primeiro contato foi ultrapassado.",
                        ),
                        42,
                    )
                elif "awaiting_first_contact" in sla.reasons:
                    add(
                        Candidate(
                            75,
                            "first_contact",
                            "Realizar primeiro contato",
                            "awaiting_first_contact",
                            "O lead ainda não recebeu o primeiro contato.",
                        ),
                        20,
                    )
                if sla.overdue_followups > 0:
                    add(
                        Candidate(
                            95,
                            "follow_up",
                            "Executar retorno vencido",
                            "overdue_followup",
                            f"Há {sla.overdue_followups} retorno(s) vencido(s).",
                        ),
                        36,
                    )
                if sla.stale:
                    add(
                        Candidate(
                            72,
                            "reengage",
                            "Reengajar lead",
                            "stale_lead",
                            "O lead está há tempo demais sem contato recente.",
                        ),
                        24,
                    )
            if opportunity_at_risk:
                add(
                    Candidate(
                        88,
                        "recover_opportunity",
                        "Recuperar negociação",
                        "opportunity_at_risk",
                        (
                            "Existe uma oportunidade aberta sem atualização "
                            "há pelo menos 3 dias."
                        ),
                    ),
                    30,
                )
            elif opportunity is not None:
                add(
                    Candidate(
                        45,
                        "advance_opportunity",
                        "Avançar negociação",
                        "open_opportunity",
                        "Há uma oportunidade aberta que pode avançar no pipeline.",
                    ),
                    10,
                )
            if (
                not active_cadence
                and lead.id in last_contact
                and opportunity is None
                and not waiting_whatsapp
            ):
                add(
                    Candidate(
                        35,
                        "enroll_cadence",
                        "Incluir em cadência",
                        "no_active_cadence",
                        (
                            "O lead já foi contatado e não participa de uma "
                            "cadência ativa."
                        ),
                    ),
                    6,
                )
            if not candidates:
                add(
                    Candidate(
                        10,
                        "review_lead",
                        "Revisar próximo passo",
                        "healthy_lead",
                        "Não há pendência crítica; revise a próxima ação comercial.",
                    ),
                    2,
                )

            best = max(candidates, key=lambda item: item.weight)
            score = min(100, score)
            item_urgency = self._urgency(score)
            if urgency and item_urgency != urgency:
                continue
            if action and best.action != action:
                continue

            suggested_channel = (
                "manual"
                if best.action == "assign_owner"
                else self._channel(lead, waiting_whatsapp=waiting_whatsapp)
            )
            items.append(
                {
                    "lead_public_id": lead.public_id,
                    "lead_name": lead.name,
                    "interest": lead.interest,
                    "status": lead.status,
                    "priority": lead.priority,
                    "source": lead.source,
                    "owner_user_public_id": owner_public_id,
                    "owner_name": owner_name,
                    "action": best.action,
                    "action_title": best.title,
                    "urgency": item_urgency,
                    "score": score,
                    "suggested_channel": suggested_channel,
                    "suggested_contact_window": contact_window,
                    "reasons": reasons,
                    "reason_codes": reason_codes,
                    "last_contact_at": last_contact.get(lead.id),
                    "last_whatsapp_at": latest_message_at,
                    "awaiting_whatsapp_reply": waiting_whatsapp,
                    "active_cadence": active_cadence,
                    "open_opportunity_public_id": (
                        opportunity.public_id if opportunity is not None else None
                    ),
                    "open_opportunity_stage": (
                        opportunity.stage if opportunity is not None else None
                    ),
                    "open_opportunity_value": (
                        float(opportunity.value_amount)
                        if opportunity is not None
                        else None
                    ),
                    "opportunity_at_risk": opportunity_at_risk,
                }
            )

        items.sort(
            key=lambda item: (
                -int(item["score"]),
                str(item["lead_name"]).casefold(),
            )
        )
        items = items[:limit]
        metrics = {
            "total_leads": len(items),
            "critical": sum(item["urgency"] == "critical" for item in items),
            "high": sum(item["urgency"] == "high" for item in items),
            "medium": sum(item["urgency"] == "medium" for item in items),
            "low": sum(item["urgency"] == "low" for item in items),
            "awaiting_reply": sum(
                bool(item["awaiting_whatsapp_reply"]) for item in items
            ),
            "overdue_followups": sum(
                "overdue_followup" in item["reason_codes"] for item in items
            ),
            "unassigned": sum(
                item["owner_user_public_id"] is None for item in items
            ),
            "opportunities_at_risk": sum(
                bool(item["opportunity_at_risk"]) for item in items
            ),
        }
        return {
            "generated_at": now,
            "suggested_contact_window": contact_window,
            "metrics": metrics,
            "items": items,
        }
