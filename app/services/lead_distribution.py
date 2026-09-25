from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.audit import lead_snapshot
from app.models import (
    Lead,
    LeadDistributionConfig,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.permissions import VALID_ROLES
from app.repositories import (
    LeadDistributionConfigRepository,
    LeadRepository,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.schemas.lead_distribution import (
    LeadDistributionConfigUpdate,
    LeadDistributionRule,
)
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError


class LeadDistributionConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DistributionMemberView:
    membership: WorkspaceMembership
    user: User
    assigned_active_leads: int
    eligible: bool


@dataclass(frozen=True)
class DistributionAssignment:
    lead_public_id: str
    user_public_id: str
    user_name: str
    strategy: str
    rule_name: str | None
    previous_load: int


@dataclass(frozen=True)
class DistributionSummary:
    config: LeadDistributionConfigUpdate
    members: list[DistributionMemberView]
    unassigned_active_leads: int
    total_active_leads: int


@dataclass(frozen=True)
class DistributionRunResult:
    dry_run: bool
    scanned: int
    assigned: int
    skipped: int
    assignments: list[DistributionAssignment]


class LeadDistributionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.configs = LeadDistributionConfigRepository(db)
        self.leads = LeadRepository(db)
        self.users = UserRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str) -> Workspace:
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(f"Empresa não encontrada: {public_id}")
        return workspace

    @staticmethod
    def _default_payload() -> LeadDistributionConfigUpdate:
        return LeadDistributionConfigUpdate(
            enabled=False,
            strategy="least_loaded",
            eligible_roles=["seller"],
            eligible_user_public_ids=[],
            rules=[],
        )

    @staticmethod
    def _payload_from_model(
        config: LeadDistributionConfig | None,
    ) -> LeadDistributionConfigUpdate:
        if config is None:
            return LeadDistributionService._default_payload()
        return LeadDistributionConfigUpdate(
            enabled=config.enabled,
            strategy=config.strategy,
            eligible_roles=list(config.eligible_roles or []),
            eligible_user_public_ids=list(config.eligible_user_public_ids or []),
            rules=list(config.rules or []),
        )

    def get_config(self, workspace_public_id: str) -> LeadDistributionConfigUpdate:
        workspace = self._workspace(workspace_public_id)
        return self._payload_from_model(
            self.configs.get_by_workspace_id(workspace.id)
        )

    def _workspace_members(
        self,
        workspace_id: int,
    ) -> list[tuple[WorkspaceMembership, User]]:
        return self.memberships.list_for_workspace(workspace_id)

    def _validate_user_ids(
        self,
        *,
        workspace_id: int,
        user_public_ids: set[str],
    ) -> None:
        if not user_public_ids:
            return
        available = {
            user.public_id
            for membership, user in self._workspace_members(workspace_id)
            if membership.active and user.active
        }
        missing = sorted(user_public_ids - available)
        if missing:
            raise LeadDistributionConfigError(
                "Usuários elegíveis não possuem acesso ativo à empresa: "
                + ", ".join(missing)
            )

    def save_config(
        self,
        workspace_public_id: str,
        payload: LeadDistributionConfigUpdate,
    ) -> LeadDistributionConfigUpdate:
        workspace = self._workspace(workspace_public_id)

        invalid_roles = sorted(set(payload.eligible_roles) - VALID_ROLES)
        if invalid_roles:
            raise LeadDistributionConfigError(
                "Perfis inválidos: " + ", ".join(invalid_roles)
            )

        configured_users = set(payload.eligible_user_public_ids)
        for rule in payload.rules:
            configured_users.update(rule.eligible_user_public_ids)
        self._validate_user_ids(
            workspace_id=workspace.id,
            user_public_ids=configured_users,
        )

        config = self.configs.get_by_workspace_id(workspace.id)
        values = payload.model_dump(mode="json")
        if config is None:
            config = self.configs.create(
                workspace_id=workspace.id,
                **values,
            )
        else:
            config.enabled = payload.enabled
            config.strategy = payload.strategy
            config.eligible_roles = list(payload.eligible_roles)
            config.eligible_user_public_ids = list(
                payload.eligible_user_public_ids
            )
            config.rules = [rule.model_dump(mode="json") for rule in payload.rules]
            self.configs.save(config)

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead_distribution",
            entity_public_id=workspace.public_id,
            action="lead_distribution.config_updated",
            after_data={
                "enabled": payload.enabled,
                "strategy": payload.strategy,
                "eligible_roles": list(payload.eligible_roles),
                "eligible_user_public_ids": list(
                    payload.eligible_user_public_ids
                ),
                "rules_count": len(payload.rules),
            },
        )
        self.db.commit()
        return self._payload_from_model(config)

    @staticmethod
    def _base_eligible(
        *,
        membership: WorkspaceMembership,
        user: User,
        payload: LeadDistributionConfigUpdate,
    ) -> bool:
        if not membership.active or not user.active:
            return False
        if membership.role not in payload.eligible_roles:
            return False
        return (
            not payload.eligible_user_public_ids
            or user.public_id in payload.eligible_user_public_ids
        )

    def summary(self, workspace_public_id: str) -> DistributionSummary:
        workspace = self._workspace(workspace_public_id)
        config_model = self.configs.get_by_workspace_id(workspace.id)
        payload = self._payload_from_model(config_model)
        loads = self.leads.active_loads_by_owner(workspace.id)
        total, unassigned = self.leads.active_counts(workspace.id)

        members = [
            DistributionMemberView(
                membership=membership,
                user=user,
                assigned_active_leads=loads.get(membership.id, 0),
                eligible=self._base_eligible(
                    membership=membership,
                    user=user,
                    payload=payload,
                ),
            )
            for membership, user in self._workspace_members(workspace.id)
        ]

        return DistributionSummary(
            config=payload,
            members=members,
            unassigned_active_leads=unassigned,
            total_active_leads=total,
        )

    @staticmethod
    def _matches_rule(lead: Lead, rule: LeadDistributionRule) -> bool:
        if not rule.enabled:
            return False
        if rule.source and lead.source != rule.source:
            return False
        if rule.channel and lead.channel != rule.channel:
            return False
        if rule.priorities and lead.priority not in rule.priorities:
            return False

        if rule.campaign_contains:
            campaign = (lead.campaign or "").casefold()
            if rule.campaign_contains.casefold() not in campaign:
                return False

        if rule.interest_contains:
            values = [lead.interest or ""]
            values.extend(str(value) for value in (lead.custom_fields or {}).values())
            haystack = " ".join(values).casefold()
            if rule.interest_contains.casefold() not in haystack:
                return False

        return True

    @staticmethod
    def _filter_rule_candidates(
        candidates: list[tuple[WorkspaceMembership, User]],
        rule: LeadDistributionRule | None,
    ) -> list[tuple[WorkspaceMembership, User]]:
        if rule is None or not rule.eligible_user_public_ids:
            return candidates
        allowed = set(rule.eligible_user_public_ids)
        return [item for item in candidates if item[1].public_id in allowed]

    @staticmethod
    def _choose_round_robin(
        candidates: list[tuple[WorkspaceMembership, User]],
        last_membership_id: int | None,
    ) -> tuple[WorkspaceMembership, User]:
        ordered = sorted(candidates, key=lambda item: item[0].id)
        if last_membership_id is None:
            return ordered[0]
        for item in ordered:
            if item[0].id > last_membership_id:
                return item
        return ordered[0]

    @staticmethod
    def _choose_least_loaded(
        candidates: list[tuple[WorkspaceMembership, User]],
        loads: dict[int, int],
    ) -> tuple[WorkspaceMembership, User]:
        return min(
            candidates,
            key=lambda item: (loads.get(item[0].id, 0), item[0].id),
        )

    def _resolve_assignment(
        self,
        *,
        lead: Lead,
        config_model: LeadDistributionConfig,
        payload: LeadDistributionConfigUpdate,
        loads: dict[int, int],
    ) -> tuple[WorkspaceMembership, User, str, str | None] | None:
        candidates = [
            (membership, user)
            for membership, user in self._workspace_members(lead.workspace_id)
            if self._base_eligible(
                membership=membership,
                user=user,
                payload=payload,
            )
        ]
        if not candidates:
            return None

        matched_rule = next(
            (
                rule
                for rule in payload.rules
                if self._matches_rule(lead, rule)
            ),
            None,
        )
        rule_candidates = self._filter_rule_candidates(candidates, matched_rule)
        if rule_candidates:
            candidates = rule_candidates

        strategy = (
            matched_rule.strategy
            if matched_rule is not None and matched_rule.strategy is not None
            else payload.strategy
        )

        if strategy == "round_robin":
            membership, user = self._choose_round_robin(
                candidates,
                config_model.last_assigned_membership_id,
            )
        else:
            membership, user = self._choose_least_loaded(candidates, loads)

        return (
            membership,
            user,
            strategy,
            matched_rule.name if matched_rule is not None else None,
        )

    def _ensure_persisted_config(
        self,
        workspace_id: int,
    ) -> LeadDistributionConfig | None:
        return self.configs.get_by_workspace_id(workspace_id)

    def assign_if_enabled(
        self,
        lead: Lead,
        *,
        commit: bool = False,
    ) -> DistributionAssignment | None:
        if lead.owner_membership_id is not None or not lead.active:
            return None

        config_model = self._ensure_persisted_config(lead.workspace_id)
        if config_model is None or not config_model.enabled:
            return None

        payload = self._payload_from_model(config_model)
        loads = self.leads.active_loads_by_owner(lead.workspace_id)
        resolved = self._resolve_assignment(
            lead=lead,
            config_model=config_model,
            payload=payload,
            loads=loads,
        )
        if resolved is None:
            return None

        membership, user, strategy, rule_name = resolved
        previous_load = loads.get(membership.id, 0)
        before_data = lead_snapshot(lead, owner_user_public_id=None)

        lead.owner_membership_id = membership.id
        self.leads.save(lead)
        config_model.last_assigned_membership_id = membership.id
        self.configs.save(config_model)

        self.audit.record(
            workspace_id=lead.workspace_id,
            entity_type="lead",
            entity_public_id=lead.public_id,
            action="lead.auto_assigned",
            before_data=before_data,
            after_data=lead_snapshot(
                lead,
                owner_user_public_id=user.public_id,
            ),
            metadata={
                "strategy": strategy,
                "rule_name": rule_name,
                "previous_load": previous_load,
            },
        )

        if commit:
            self.db.commit()
            self.db.refresh(lead)

        return DistributionAssignment(
            lead_public_id=lead.public_id,
            user_public_id=user.public_id,
            user_name=user.name,
            strategy=strategy,
            rule_name=rule_name,
            previous_load=previous_load,
        )

    def run(
        self,
        workspace_public_id: str,
        *,
        limit: int,
        dry_run: bool,
    ) -> DistributionRunResult:
        workspace = self._workspace(workspace_public_id)
        config_model = self.configs.get_by_workspace_id(workspace.id)
        if config_model is None or not config_model.enabled:
            raise LeadDistributionConfigError(
                "Ative a distribuição automática antes de executar a fila."
            )

        payload = self._payload_from_model(config_model)
        leads = self.leads.list_unassigned_active(
            workspace_id=workspace.id,
            limit=limit,
        )
        loads = self.leads.active_loads_by_owner(workspace.id)
        assignments: list[DistributionAssignment] = []
        skipped = 0
        simulated_last = config_model.last_assigned_membership_id

        for lead in leads:
            if dry_run:
                original_last = config_model.last_assigned_membership_id
                config_model.last_assigned_membership_id = simulated_last
                resolved = self._resolve_assignment(
                    lead=lead,
                    config_model=config_model,
                    payload=payload,
                    loads=loads,
                )
                config_model.last_assigned_membership_id = original_last
                if resolved is None:
                    skipped += 1
                    continue
                membership, user, strategy, rule_name = resolved
                previous_load = loads.get(membership.id, 0)
                assignments.append(
                    DistributionAssignment(
                        lead_public_id=lead.public_id,
                        user_public_id=user.public_id,
                        user_name=user.name,
                        strategy=strategy,
                        rule_name=rule_name,
                        previous_load=previous_load,
                    )
                )
                loads[membership.id] = previous_load + 1
                simulated_last = membership.id
                continue

            assignment = self.assign_if_enabled(lead, commit=False)
            if assignment is None:
                skipped += 1
                continue
            assignments.append(assignment)

        if not dry_run:
            self.audit.record(
                workspace_id=workspace.id,
                entity_type="lead_distribution",
                entity_public_id=workspace.public_id,
                action="lead_distribution.batch_run",
                metadata={
                    "scanned": len(leads),
                    "assigned": len(assignments),
                    "skipped": skipped,
                },
            )
            self.db.commit()

        return DistributionRunResult(
            dry_run=dry_run,
            scanned=len(leads),
            assigned=len(assignments),
            skipped=skipped,
            assignments=assignments,
        )
