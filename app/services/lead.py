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
from app.schemas import LeadCreate, LeadUpdate
from app.segments import get_segment_definition
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError


class LeadNotFoundError(ValueError):
    pass


class LeadDuplicateError(ValueError):
    def __init__(self, lead_public_id: str) -> None:
        self.lead_public_id = lead_public_id
        super().__init__(f"Lead duplicado: {lead_public_id}")


class LeadOwnerError(ValueError):
    pass


class LeadStatusError(ValueError):
    pass


class LeadCustomFieldError(ValueError):
    pass


@dataclass(frozen=True)
class LeadView:
    lead: Lead
    owner_user_public_id: str | None


@dataclass(frozen=True)
class LeadPageView:
    items: list[LeadView]
    total: int
    page: int
    page_size: int


class LeadService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.leads = LeadRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.segment_configs = WorkspaceSegmentConfigRepository(db)
        self.audit = AuditService(db)

    @staticmethod
    def _normalize_phone(phone: str | None) -> str | None:
        if phone is None:
            return None
        digits = "".join(char for char in phone if char.isdigit())
        return digits or None

    @staticmethod
    def _normalize_email(email: str | None) -> str | None:
        if email is None:
            return None
        normalized = email.strip().lower()
        return normalized or None

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {public_id}"
            )
        return workspace

    def _pipeline_and_fields(
        self,
        workspace,
    ) -> tuple[list[str], set[str]]:
        config = self.segment_configs.get_by_workspace_id(workspace.id)

        if config is not None:
            return (
                list(config.pipeline),
                set(config.custom_fields),
            )

        definition = get_segment_definition(workspace.segment)
        if definition is None:
            return (["novo"], set())

        return (
            list(definition.pipeline),
            set(definition.custom_fields),
        )

    def _validate_status(
        self,
        status: str,
        pipeline: list[str],
    ) -> None:
        if status not in pipeline:
            raise LeadStatusError(
                f"Status '{status}' não pertence ao pipeline desta empresa."
            )

    def _validate_custom_fields(
        self,
        custom_fields: dict[str, object],
        allowed_fields: set[str],
    ) -> None:
        unknown = sorted(set(custom_fields) - allowed_fields)

        if unknown:
            fields = ", ".join(unknown)
            raise LeadCustomFieldError(
                f"Campos personalizados não permitidos: {fields}"
            )

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
            raise LeadOwnerError(
                f"Vendedor não encontrado: {user_public_id}"
            )

        membership = self.memberships.get(
            workspace_id=workspace_id,
            user_id=user.id,
        )

        if membership is None or not membership.active:
            raise LeadOwnerError(
                "O responsável não possui acesso ativo a esta empresa."
            )

        return membership.id

    def _view(self, lead: Lead) -> LeadView:
        return LeadView(
            lead=lead,
            owner_user_public_id=self.leads.owner_user_public_id(
                lead.owner_membership_id
            ),
        )

    def create(
        self,
        workspace_public_id: str,
        payload: LeadCreate,
    ) -> LeadView:
        workspace = self._workspace(workspace_public_id)
        pipeline, allowed_fields = self._pipeline_and_fields(workspace)

        status = payload.status or pipeline[0]
        self._validate_status(status, pipeline)
        self._validate_custom_fields(
            payload.custom_fields,
            allowed_fields,
        )

        normalized_phone = self._normalize_phone(payload.phone)
        normalized_email = self._normalize_email(payload.email)

        duplicate = self.leads.find_duplicate(
            workspace_id=workspace.id,
            normalized_phone=normalized_phone,
            normalized_email=normalized_email,
            external_id=payload.external_id,
        )
        if duplicate is not None:
            raise LeadDuplicateError(duplicate.public_id)

        owner_membership_id = self._owner_membership_id(
            workspace_id=workspace.id,
            user_public_id=payload.owner_user_public_id,
        )

        lead = self.leads.create(
            workspace_id=workspace.id,
            owner_membership_id=owner_membership_id,
            name=payload.name,
            phone=payload.phone,
            normalized_phone=normalized_phone,
            email=payload.email,
            normalized_email=normalized_email,
            external_id=payload.external_id,
            interest=payload.interest,
            source=payload.source,
            channel=payload.channel,
            campaign=payload.campaign,
            message=payload.message,
            status=status,
            priority=payload.priority,
            custom_fields=dict(payload.custom_fields),
            consent=payload.consent,
        )

        created_view = self._view(lead)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead",
            entity_public_id=lead.public_id,
            action="lead.created",
            after_data=lead_snapshot(
                lead,
                owner_user_public_id=created_view.owner_user_public_id,
            ),
        )

        if lead.owner_membership_id is None:
            from app.services.lead_distribution import LeadDistributionService

            LeadDistributionService(self.db).assign_if_enabled(lead)

        self.db.commit()
        self.db.refresh(lead)

        return self._view(lead)

    def list_all(
        self,
        workspace_public_id: str,
    ) -> list[LeadView]:
        workspace = self._workspace(workspace_public_id)
        return [
            self._view(lead)
            for lead in self.leads.list_for_workspace(workspace.id)
        ]

    def search(
        self,
        workspace_public_id: str,
        *,
        query: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        source: str | None = None,
        channel: str | None = None,
        campaign: str | None = None,
        owner_user_public_id: str | None = None,
        only_unassigned: bool = False,
        active: bool | None = True,
        page: int = 1,
        page_size: int = 20,
    ) -> LeadPageView:
        workspace = self._workspace(workspace_public_id)

        owner_membership_id: int | None = None
        if owner_user_public_id is not None:
            user = self.users.get_by_public_id(owner_user_public_id)
            if user is None:
                return LeadPageView(
                    items=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                )

            membership = self.memberships.get(
                workspace_id=workspace.id,
                user_id=user.id,
            )
            if membership is None:
                return LeadPageView(
                    items=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                )

            owner_membership_id = membership.id

        leads, total = self.leads.search_for_workspace(
            workspace_id=workspace.id,
            query=query,
            status=status,
            priority=priority,
            source=source,
            channel=channel,
            campaign=campaign,
            owner_membership_id=owner_membership_id,
            only_unassigned=only_unassigned,
            active=active,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        return LeadPageView(
            items=[self._view(lead) for lead in leads],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get(
        self,
        workspace_public_id: str,
        lead_public_id: str,
    ) -> LeadView:
        workspace = self._workspace(workspace_public_id)

        lead = self.leads.get_by_public_id(
            workspace_id=workspace.id,
            public_id=lead_public_id,
        )
        if lead is None:
            raise LeadNotFoundError(
                f"Lead não encontrado: {lead_public_id}"
            )

        return self._view(lead)

    def update(
        self,
        workspace_public_id: str,
        lead_public_id: str,
        payload: LeadUpdate,
    ) -> LeadView:
        workspace = self._workspace(workspace_public_id)

        lead = self.leads.get_by_public_id(
            workspace_id=workspace.id,
            public_id=lead_public_id,
        )
        if lead is None:
            raise LeadNotFoundError(
                f"Lead não encontrado: {lead_public_id}"
            )

        before_view = self._view(lead)
        before_data = lead_snapshot(
            lead,
            owner_user_public_id=before_view.owner_user_public_id,
        )

        changes = payload.model_dump(exclude_unset=True)
        pipeline, allowed_fields = self._pipeline_and_fields(workspace)

        if "status" in changes and changes["status"] is not None:
            self._validate_status(changes["status"], pipeline)

        if (
            "custom_fields" in changes
            and changes["custom_fields"] is not None
        ):
            self._validate_custom_fields(
                changes["custom_fields"],
                allowed_fields,
            )

        phone = changes.get("phone", lead.phone)
        email = changes.get("email", lead.email)
        external_id = changes.get("external_id", lead.external_id)

        normalized_phone = self._normalize_phone(phone)
        normalized_email = self._normalize_email(email)

        duplicate = self.leads.find_duplicate(
            workspace_id=workspace.id,
            normalized_phone=normalized_phone,
            normalized_email=normalized_email,
            external_id=external_id,
            exclude_lead_id=lead.id,
        )
        if duplicate is not None:
            raise LeadDuplicateError(duplicate.public_id)

        if "owner_user_public_id" in changes:
            lead.owner_membership_id = self._owner_membership_id(
                workspace_id=workspace.id,
                user_public_id=changes.pop("owner_user_public_id"),
            )

        direct_fields = (
            "name",
            "phone",
            "email",
            "external_id",
            "interest",
            "source",
            "channel",
            "campaign",
            "message",
            "status",
            "priority",
            "custom_fields",
            "consent",
            "active",
        )

        for field_name in direct_fields:
            if field_name in changes:
                setattr(lead, field_name, changes[field_name])

        lead.normalized_phone = normalized_phone
        lead.normalized_email = normalized_email

        self.leads.save(lead)

        after_view = self._view(lead)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead",
            entity_public_id=lead.public_id,
            action="lead.updated",
            before_data=before_data,
            after_data=lead_snapshot(
                lead,
                owner_user_public_id=after_view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(lead)

        return self._view(lead)

    def deactivate(
        self,
        workspace_public_id: str,
        lead_public_id: str,
    ) -> LeadView:
        view = self.get(
            workspace_public_id,
            lead_public_id,
        )

        before_data = lead_snapshot(
            view.lead,
            owner_user_public_id=view.owner_user_public_id,
        )

        view.lead.active = False
        self.leads.save(view.lead)

        self.audit.record(
            workspace_id=view.lead.workspace_id,
            entity_type="lead",
            entity_public_id=view.lead.public_id,
            action="lead.deactivated",
            before_data=before_data,
            after_data=lead_snapshot(
                view.lead,
                owner_user_public_id=view.owner_user_public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(view.lead)

        return self._view(view.lead)

    def intake(
        self,
        workspace_public_id: str,
        payload: LeadCreate,
    ) -> tuple[str, LeadView]:
        workspace = self._workspace(workspace_public_id)

        normalized_phone = self._normalize_phone(payload.phone)
        normalized_email = self._normalize_email(payload.email)

        duplicate = self.leads.find_duplicate(
            workspace_id=workspace.id,
            normalized_phone=normalized_phone,
            normalized_email=normalized_email,
            external_id=payload.external_id,
        )

        if duplicate is None:
            return "created", self.create(
                workspace_public_id,
                payload,
            )

        update_values: dict[str, object] = {
            "name": payload.name,
            "source": payload.source,
            "channel": payload.channel,
            "priority": payload.priority,
            "consent": payload.consent,
            "active": True,
        }

        optional_values = {
            "phone": payload.phone,
            "email": payload.email,
            "external_id": payload.external_id,
            "interest": payload.interest,
            "campaign": payload.campaign,
            "message": payload.message,
            "owner_user_public_id": payload.owner_user_public_id,
        }

        for field_name, value in optional_values.items():
            if value is not None:
                update_values[field_name] = value

        if payload.custom_fields:
            merged_custom_fields = {
                **duplicate.custom_fields,
                **payload.custom_fields,
            }
            update_values["custom_fields"] = merged_custom_fields

        update = LeadUpdate(**update_values)

        view = self.update(
            workspace_public_id,
            duplicate.public_id,
            update,
        )

        if view.lead.owner_membership_id is None:
            from app.services.lead_distribution import LeadDistributionService

            assignment = LeadDistributionService(self.db).assign_if_enabled(
                view.lead,
                commit=True,
            )
            if assignment is not None:
                view = self._view(view.lead)

        return "duplicate_updated", view
