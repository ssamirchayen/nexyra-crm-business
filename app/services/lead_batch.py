from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.audit import lead_snapshot
from app.models import Lead
from app.repositories import (
    LeadRepository,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
    WorkspaceSegmentConfigRepository,
)
from app.schemas.lead_batch import LeadBatchRequest
from app.segments import get_segment_definition
from app.services.audit import AuditService
from app.services.lead import LeadNotFoundError, LeadOwnerError, LeadStatusError
from app.services.workspace import WorkspaceNotFoundError


@dataclass(frozen=True)
class LeadBatchItem:
    lead_public_id: str
    lead_name: str
    changed: bool
    changed_fields: list[str]
    before_status: str
    after_status: str
    before_priority: str
    after_priority: str
    before_owner_user_public_id: str | None
    after_owner_user_public_id: str | None
    before_active: bool
    after_active: bool


@dataclass(frozen=True)
class LeadBatchResult:
    dry_run: bool
    requested: int
    found: int
    changed: int
    unchanged: int
    items: list[LeadBatchItem]


class LeadBatchService:
    def __init__(self, db: Session) -> None:
        self.db = db
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

    def _owner_membership_id(
        self,
        *,
        workspace_id: int,
        user_public_id: str,
    ) -> int:
        user = self.users.get_by_public_id(user_public_id)
        if user is None:
            raise LeadOwnerError(
                f"Responsável não encontrado: {user_public_id}"
            )
        membership = self.memberships.get(
            workspace_id=workspace_id,
            user_id=user.id,
        )
        if membership is None or not membership.active or not user.active:
            raise LeadOwnerError(
                "O responsável não possui acesso ativo a esta empresa."
            )
        return membership.id

    def run(
        self,
        workspace_public_id: str,
        payload: LeadBatchRequest,
    ) -> LeadBatchResult:
        workspace = self._workspace(workspace_public_id)
        pipeline = self._pipeline(workspace)

        if payload.status is not None and payload.status not in pipeline:
            raise LeadStatusError(
                f"Status '{payload.status}' não pertence ao pipeline desta empresa."
            )

        target_owner_membership_id: int | None = None
        target_owner_user_public_id: str | None = None
        if payload.owner_mode == "assign":
            assert payload.owner_user_public_id is not None
            target_owner_membership_id = self._owner_membership_id(
                workspace_id=workspace.id,
                user_public_id=payload.owner_user_public_id,
            )
            target_owner_user_public_id = payload.owner_user_public_id

        leads: list[Lead] = []
        for public_id in payload.lead_public_ids:
            lead = self.leads.get_by_public_id(
                workspace_id=workspace.id,
                public_id=public_id,
            )
            if lead is None:
                raise LeadNotFoundError(f"Lead não encontrado: {public_id}")
            leads.append(lead)

        items: list[LeadBatchItem] = []
        changed_count = 0

        for lead in leads:
            before_owner = self.leads.owner_user_public_id(
                lead.owner_membership_id
            )
            before_snapshot = lead_snapshot(
                lead,
                owner_user_public_id=before_owner,
            )

            after_status = payload.status or lead.status
            after_priority = payload.priority or lead.priority
            after_active = lead.active if payload.active is None else payload.active
            after_owner_membership_id = lead.owner_membership_id
            after_owner_user_public_id = before_owner

            if payload.owner_mode == "assign":
                after_owner_membership_id = target_owner_membership_id
                after_owner_user_public_id = target_owner_user_public_id
            elif payload.owner_mode == "clear":
                after_owner_membership_id = None
                after_owner_user_public_id = None

            changed_fields: list[str] = []
            if after_status != lead.status:
                changed_fields.append("status")
            if after_priority != lead.priority:
                changed_fields.append("priority")
            if after_owner_membership_id != lead.owner_membership_id:
                changed_fields.append("owner")
            if after_active != lead.active:
                changed_fields.append("active")

            changed = bool(changed_fields)
            if changed:
                changed_count += 1

            item = LeadBatchItem(
                lead_public_id=lead.public_id,
                lead_name=lead.name,
                changed=changed,
                changed_fields=changed_fields,
                before_status=lead.status,
                after_status=after_status,
                before_priority=lead.priority,
                after_priority=after_priority,
                before_owner_user_public_id=before_owner,
                after_owner_user_public_id=after_owner_user_public_id,
                before_active=lead.active,
                after_active=after_active,
            )
            items.append(item)

            if payload.dry_run or not changed:
                continue

            lead.status = after_status
            lead.priority = after_priority
            lead.owner_membership_id = after_owner_membership_id
            lead.active = after_active
            self.leads.save(lead)

            self.audit.record(
                workspace_id=workspace.id,
                entity_type="lead",
                entity_public_id=lead.public_id,
                action="lead.batch_updated",
                before_data=before_snapshot,
                after_data=lead_snapshot(
                    lead,
                    owner_user_public_id=after_owner_user_public_id,
                ),
                metadata={
                    "changed_fields": changed_fields,
                    "batch_size": len(leads),
                },
            )

        if not payload.dry_run:
            self.db.commit()

        return LeadBatchResult(
            dry_run=payload.dry_run,
            requested=len(payload.lead_public_ids),
            found=len(leads),
            changed=changed_count,
            unchanged=len(leads) - changed_count,
            items=items,
        )
