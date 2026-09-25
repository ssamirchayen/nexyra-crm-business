from __future__ import annotations

from collections import Counter
from datetime import timezone

from sqlalchemy.orm import Session

from app.audit import activity_snapshot, lead_snapshot, opportunity_snapshot
from app.integrations.atlas.contract import (
    ATLAS_CAPABILITIES,
    ATLAS_CONTRACT_NAME,
    SUPPORTED_ATLAS_ACTIONS,
)
from app.integrations.atlas.schemas import (
    AtlasActionExecuteRequest,
    AtlasActionRequest,
)
from app.models import Activity
from app.repositories import (
    ActivityRepository,
    LeadRepository,
    OpportunityRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
    WorkspaceSegmentConfigRepository,
)
from app.schemas import ActivityCreate, LeadCreate, LeadUpdate, OpportunityMove
from app.segments import get_segment_definition
from app.services.activity import ActivityService
from app.services.audit import AuditService
from app.services.lead import LeadService
from app.services.opportunity import OpportunityService


class AtlasActionValidationError(ValueError):
    pass


class AtlasConfirmationRequiredError(ValueError):
    pass


class AtlasIntegrationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.segment_configs = WorkspaceSegmentConfigRepository(db)
        self.leads = LeadRepository(db)
        self.opportunities = OpportunityRepository(db)
        self.activities = ActivityRepository(db)
        self.audit = AuditService(db)

    @staticmethod
    def capabilities(
        *,
        contract_version: str,
    ) -> dict[str, object]:
        return {
            "contract_name": ATLAS_CONTRACT_NAME,
            "contract_version": contract_version,
            "capabilities": list(ATLAS_CAPABILITIES),
            "supported_actions": list(SUPPORTED_ATLAS_ACTIONS),
            "confirmation_required_for_execution": True,
            "supported_actor_types": [
                "system",
                "user",
                "atlas",
                "integration",
            ],
        }

    def workspace_context(
        self,
        *,
        workspace,
        actor_user,
        membership,
        permissions: tuple[str, ...],
        contract_version: str,
    ) -> dict[str, object]:
        config = self.segment_configs.get_by_workspace_id(workspace.id)

        if config is not None:
            segment_data = {
                "code": config.segment_code,
                "interest_label": config.interest_label,
                "pipeline": list(config.pipeline),
                "custom_fields": list(config.custom_fields),
            }
        else:
            definition = get_segment_definition(workspace.segment)
            segment_data = {
                "code": workspace.segment,
                "interest_label": (
                    definition.interest_label
                    if definition is not None
                    else "Interesse"
                ),
                "pipeline": (
                    list(definition.pipeline)
                    if definition is not None
                    else ["novo"]
                ),
                "custom_fields": (
                    list(definition.custom_fields)
                    if definition is not None
                    else []
                ),
            }

        member_rows = self.memberships.list_for_workspace(workspace.id)
        members = [
            {
                "user_public_id": user.public_id,
                "name": user.name,
                "role": item.role,
                "active": bool(item.active and user.active),
            }
            for item, user in member_rows
        ]

        leads = self.leads.list_for_workspace(workspace.id)
        opportunities = self.opportunities.list_for_workspace(workspace.id)
        pending = self.activities.pending_for_workspace(workspace.id)

        source_counter = Counter(
            (lead.source, lead.channel)
            for lead in leads
            if lead.active
        )
        lead_sources = [
            {
                "source": source,
                "channel": channel,
                "lead_count": count,
            }
            for (source, channel), count in sorted(
                source_counter.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

        pending_followups = [
            self._pending_activity_summary(item)
            for item in pending[:25]
        ]

        return {
            "contract_version": contract_version,
            "workspace": {
                "public_id": workspace.public_id,
                "name": workspace.name,
                "slug": workspace.slug,
                "segment": workspace.segment,
                "active": workspace.active,
            },
            "segment": segment_data,
            "actor": {
                "user_public_id": actor_user.public_id,
                "name": actor_user.name,
                "role": membership.role,
                "permissions": list(permissions),
            },
            "members": members,
            "counts": {
                "leads": len(leads),
                "active_leads": sum(1 for lead in leads if lead.active),
                "opportunities": len(opportunities),
                "pending_followups": len(pending),
            },
            "opportunity_metrics": self.opportunities.metrics(
                workspace.id
            ),
            "lead_sources": lead_sources,
            "pending_followups": pending_followups,
        }

    def intake_lead(
        self,
        *,
        workspace,
        actor_membership,
        payload: LeadCreate,
    ) -> tuple[str, dict[str, object]]:
        action, view = LeadService(self.db).intake(
            workspace.public_id,
            payload,
        )

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead",
            entity_public_id=view.lead.public_id,
            action="integration.lead_intake",
            actor_type="integration",
            actor_membership_id=actor_membership.id,
            after_data=lead_snapshot(
                view.lead,
                owner_user_public_id=view.owner_user_public_id,
            ),
            metadata={
                "intake_action": action,
                "source": view.lead.source,
                "channel": view.lead.channel,
                "campaign": view.lead.campaign,
                "contract": ATLAS_CONTRACT_NAME,
            },
        )
        self.db.commit()

        return action, lead_snapshot(
            view.lead,
            owner_user_public_id=view.owner_user_public_id,
        )

    def preview_action(
        self,
        *,
        workspace,
        request: AtlasActionRequest,
        contract_version: str,
    ) -> dict[str, object]:
        normalized_payload, summary = self._validate_action(
            workspace=workspace,
            request=request,
        )

        return {
            "contract_version": contract_version,
            "action": request.action,
            "target_public_id": request.target_public_id,
            "allowed": True,
            "confirmation_required": True,
            "summary": summary,
            "normalized_payload": normalized_payload,
        }

    def execute_action(
        self,
        *,
        workspace,
        actor_user,
        actor_membership,
        request: AtlasActionExecuteRequest,
        contract_version: str,
    ) -> dict[str, object]:
        if not request.confirmed:
            raise AtlasConfirmationRequiredError(
                "A execução exige confirmação explícita."
            )

        normalized_payload, _ = self._validate_action(
            workspace=workspace,
            request=request,
        )

        result = self._execute(
            workspace=workspace,
            actor_user=actor_user,
            request=request,
            normalized_payload=normalized_payload,
        )

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="atlas_action",
            entity_public_id=(
                request.target_public_id or request.action
            ),
            action="atlas.action.executed",
            actor_type="atlas",
            actor_membership_id=actor_membership.id,
            after_data=result,
            metadata={
                "contract": ATLAS_CONTRACT_NAME,
                "contract_version": contract_version,
                "action": request.action,
                "reason": request.reason,
                "payload": normalized_payload,
            },
        )
        self.db.commit()

        return {
            "contract_version": contract_version,
            "action": request.action,
            "target_public_id": request.target_public_id,
            "executed": True,
            "result": result,
        }

    def _validate_action(
        self,
        *,
        workspace,
        request: AtlasActionRequest,
    ) -> tuple[dict[str, object], str]:
        if request.action == "lead.update":
            target = self._require_target(request)
            lead = self.leads.get_by_public_id(
                workspace_id=workspace.id,
                public_id=target,
            )
            if lead is None:
                raise AtlasActionValidationError(
                    f"Lead não encontrado: {target}"
                )

            payload = LeadUpdate(**request.payload)
            normalized = payload.model_dump(
                exclude_unset=True,
                mode="json",
            )
            if not normalized:
                raise AtlasActionValidationError(
                    "Informe ao menos uma alteração para o lead."
                )

            return normalized, f"Atualizar lead {target}."

        if request.action == "opportunity.move":
            target = self._require_target(request)
            opportunity = self.opportunities.get_by_public_id(
                workspace_id=workspace.id,
                public_id=target,
            )
            if opportunity is None:
                raise AtlasActionValidationError(
                    f"Oportunidade não encontrada: {target}"
                )
            if opportunity.status != "open":
                raise AtlasActionValidationError(
                    "A oportunidade já está encerrada."
                )

            move = OpportunityMove(**request.payload)
            pipeline = self._pipeline(workspace)
            if move.to_stage not in pipeline:
                raise AtlasActionValidationError(
                    f"Etapa '{move.to_stage}' não pertence ao pipeline."
                )

            normalized = {
                "to_stage": move.to_stage,
                "note": move.note,
            }
            return normalized, (
                f"Mover oportunidade {target} de "
                f"{opportunity.stage} para {move.to_stage}."
            )

        if request.action == "activity.create":
            activity = ActivityCreate(**request.payload)
            self._validate_activity_targets(
                workspace_id=workspace.id,
                payload=activity,
            )
            normalized = activity.model_dump(
                exclude_none=True,
                mode="json",
            )
            return normalized, (
                f"Criar atividade '{activity.title}' "
                f"({activity.activity_type})."
            )

        if request.action == "activity.complete":
            target = self._require_target(request)
            activity = self.activities.get(workspace.id, target)
            if activity is None:
                raise AtlasActionValidationError(
                    f"Atividade não encontrada: {target}"
                )
            if activity.status != "pending":
                raise AtlasActionValidationError(
                    "A atividade não está pendente."
                )
            if request.payload:
                raise AtlasActionValidationError(
                    "activity.complete não aceita payload."
                )
            return {}, f"Concluir atividade {target}."

        raise AtlasActionValidationError(
            f"Ação não suportada: {request.action}"
        )

    def _execute(
        self,
        *,
        workspace,
        actor_user,
        request: AtlasActionExecuteRequest,
        normalized_payload: dict[str, object],
    ) -> dict[str, object]:
        if request.action == "lead.update":
            view = LeadService(self.db).update(
                workspace.public_id,
                self._require_target(request),
                LeadUpdate(**normalized_payload),
            )
            return lead_snapshot(
                view.lead,
                owner_user_public_id=view.owner_user_public_id,
            )

        if request.action == "opportunity.move":
            move = OpportunityMove(
                **normalized_payload,
                changed_by_user_public_id=actor_user.public_id,
            )
            view = OpportunityService(self.db).move(
                workspace.public_id,
                self._require_target(request),
                move,
            )
            return opportunity_snapshot(
                view.opportunity,
                lead_public_id=view.lead_public_id,
                owner_user_public_id=view.owner_user_public_id,
            )

        if request.action == "activity.create":
            activity = ActivityCreate(**normalized_payload)
            view = ActivityService(self.db).create(
                workspace.public_id,
                activity,
            )
            return activity_snapshot(
                view.activity,
                lead_public_id=view.lead_public_id,
                opportunity_public_id=view.opportunity_public_id,
                owner_user_public_id=view.owner_user_public_id,
            )

        if request.action == "activity.complete":
            view = ActivityService(self.db).complete(
                workspace.public_id,
                self._require_target(request),
            )
            return activity_snapshot(
                view.activity,
                lead_public_id=view.lead_public_id,
                opportunity_public_id=view.opportunity_public_id,
                owner_user_public_id=view.owner_user_public_id,
            )

        raise AtlasActionValidationError(
            f"Ação não suportada: {request.action}"
        )

    @staticmethod
    def _require_target(request: AtlasActionRequest) -> str:
        if request.target_public_id is None:
            raise AtlasActionValidationError(
                f"A ação {request.action} exige target_public_id."
            )
        return request.target_public_id

    def _pipeline(self, workspace) -> list[str]:
        config = self.segment_configs.get_by_workspace_id(workspace.id)
        if config is not None:
            return list(config.pipeline)

        definition = get_segment_definition(workspace.segment)
        if definition is None:
            return ["novo"]
        return list(definition.pipeline)

    def _validate_activity_targets(
        self,
        *,
        workspace_id: int,
        payload: ActivityCreate,
    ) -> None:
        lead = None
        opportunity = None

        if payload.lead_public_id is not None:
            lead = self.leads.get_by_public_id(
                workspace_id=workspace_id,
                public_id=payload.lead_public_id,
            )
            if lead is None:
                raise AtlasActionValidationError(
                    "Lead da atividade não pertence a esta empresa."
                )

        if payload.opportunity_public_id is not None:
            opportunity = self.opportunities.get_by_public_id(
                workspace_id=workspace_id,
                public_id=payload.opportunity_public_id,
            )
            if opportunity is None:
                raise AtlasActionValidationError(
                    "Oportunidade da atividade não pertence a esta empresa."
                )

        if (
            lead is not None
            and opportunity is not None
            and opportunity.lead_id != lead.id
        ):
            raise AtlasActionValidationError(
                "A oportunidade não pertence ao lead informado."
            )

    def _pending_activity_summary(
        self,
        activity: Activity,
    ) -> dict[str, object]:
        due_at = activity.due_at
        overdue = ActivityService.is_overdue(activity)

        if due_at is not None and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)

        return {
            "public_id": activity.public_id,
            "activity_type": activity.activity_type,
            "title": activity.title,
            "due_at": due_at.isoformat() if due_at else None,
            "overdue": overdue,
            "lead_public_id": self.activities.lead_public_id(
                activity.lead_id
            ),
            "opportunity_public_id": (
                self.activities.opportunity_public_id(
                    activity.opportunity_id
                )
            ),
            "owner_user_public_id": (
                self.activities.owner_user_public_id(
                    activity.owner_membership_id
                )
            ),
        }
