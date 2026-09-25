from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import membership_snapshot
from app.core.config import get_settings
from app.models import (
    Activity,
    Lead,
    Opportunity,
    User,
    UserCredential,
    Workspace,
    WorkspaceMembership,
)
from app.permissions import get_permissions_for_role
from app.repositories import (
    UserCredentialRepository,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.schemas import WorkspaceMembershipUpdate, WorkspaceUserCreate
from app.security import hash_password
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError


class UserNotFoundError(ValueError):
    pass


class MembershipNotFoundError(ValueError):
    pass


class MembershipPermissionError(ValueError):
    pass


class MembershipConflictError(ValueError):
    pass


@dataclass(frozen=True)
class WorkspaceUserView:
    user: User
    membership: WorkspaceMembership


class WorkspaceUserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.users = UserRepository(db)
        self.credentials = UserCredentialRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str):
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise WorkspaceNotFoundError(f"Empresa não encontrada: {public_id}")
        return workspace

    def _lock_workspace(self, workspace_id: int) -> None:
        # Serialize membership writes per workspace in PostgreSQL. A shared row
        # prevents two admins from simultaneously removing the last two admins.
        self.db.execute(
            select(Workspace.id)
            .where(
                Workspace.id == workspace_id,
            )
            .with_for_update()
        ).scalar_one()

    def _authorize_change(
        self,
        workspace_id: int,
        *,
        target: WorkspaceMembership | None = None,
        role: str | None = None,
        active: bool | None = None,
    ) -> None:
        actor_id = self.db.info.get("audit_actor_membership_id")
        if actor_id is None:
            # Existing local provisioning/bootstrap has no authenticated actor.
            return
        actor = self.db.scalar(
            select(WorkspaceMembership)
            .join(User)
            .where(
                WorkspaceMembership.id == actor_id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.active.is_(True),
                User.active.is_(True),
            )
            .execution_options(populate_existing=True)
        )
        if actor is None or actor.role not in {"admin", "manager"}:
            raise MembershipPermissionError("Você não pode alterar esta equipe.")
        if actor.role == "admin":
            return
        if role in {"admin", "manager"} or (
            target is not None and target.role in {"admin", "manager"}
        ):
            raise MembershipPermissionError(
                "Somente administradores podem gerenciar administradores e gestores."
            )
        if target is not None and active is not None and active != target.active:
            raise MembershipPermissionError(
                "Somente administradores podem desativar ou reativar membros."
            )

    def _protect_last_admin(
        self,
        view: WorkspaceUserView,
        changes: dict[str, object],
    ) -> None:
        membership = view.membership
        if not (membership.active and view.user.active and membership.role == "admin"):
            return
        if changes.get("role", "admin") == "admin" and changes.get("active", True):
            return
        others = (
            select(WorkspaceMembership.id)
            .join(User)
            .where(
                WorkspaceMembership.workspace_id == membership.workspace_id,
                WorkspaceMembership.id != membership.id,
                WorkspaceMembership.role == "admin",
                WorkspaceMembership.active.is_(True),
                User.active.is_(True),
            )
        )
        if self.credentials.get_by_user_id(view.user.id) is not None:
            # An administrator without a credential cannot keep access available.
            others = others.join(UserCredential, UserCredential.user_id == User.id)
        if self.db.scalar(others.limit(1)) is None:
            raise MembershipConflictError(
                "Mantenha pelo menos um administrador ativo com senha configurada. "
                "Configure outro administrador antes de alterar este acesso."
            )

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _conversion_rate(won: int, lost: int) -> float:
        closed = won + lost
        if closed == 0:
            return 0.0
        return round((won / closed) * 100, 2)

    def create_member(
        self,
        workspace_public_id: str,
        payload: WorkspaceUserCreate,
    ) -> WorkspaceUserView:
        workspace = self._workspace(workspace_public_id)
        self._lock_workspace(workspace.id)
        self._authorize_change(workspace.id, role=payload.role)
        user = self.users.get_by_email(payload.email)

        if user is None:
            user = self.users.create(
                name=payload.name,
                email=payload.email,
            )

        # Coordinate global account changes with membership additions.
        self.db.refresh(user, with_for_update={"key_share": True})

        if (
            self.memberships.get(
                workspace_id=workspace.id,
                user_id=user.id,
            )
            is not None
        ):
            raise MembershipConflictError("Este usuário já pertence a esta empresa.")

        if payload.initial_password is not None:
            existing_credential = self.credentials.get_by_user_id(user.id)
            if existing_credential is not None:
                raise MembershipConflictError(
                    "Este usuário já possui senha configurada. "
                    "Adicione-o sem informar uma nova senha."
                )
            self.credentials.create(
                user_id=user.id,
                password_hash=hash_password(
                    payload.initial_password,
                    iterations=self.settings.auth_password_iterations,
                ),
                must_change_password=True,
            )

        membership = self.memberships.create(
            workspace_id=workspace.id,
            user_id=user.id,
            role=payload.role,
        )

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="membership",
            entity_public_id=user.public_id,
            action="membership.created",
            after_data=membership_snapshot(
                membership,
                user_public_id=user.public_id,
            ),
        )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise MembershipConflictError(
                "Não foi possível criar o vínculo do usuário."
            ) from exc

        self.db.refresh(user)
        self.db.refresh(membership)
        return WorkspaceUserView(
            user=user,
            membership=membership,
        )

    def list_members(
        self,
        workspace_public_id: str,
    ) -> list[WorkspaceUserView]:
        workspace = self._workspace(workspace_public_id)

        return [
            WorkspaceUserView(
                user=user,
                membership=membership,
            )
            for membership, user in self.memberships.list_for_workspace(workspace.id)
        ]

    def get_member(
        self,
        workspace_public_id: str,
        user_public_id: str,
    ) -> WorkspaceUserView:
        workspace = self._workspace(workspace_public_id)
        user = self.users.get_by_public_id(user_public_id)

        if user is None:
            raise UserNotFoundError(f"Usuário não encontrado: {user_public_id}")

        membership = self.memberships.get(
            workspace_id=workspace.id,
            user_id=user.id,
        )
        if membership is None:
            raise MembershipNotFoundError("Usuário não pertence a esta empresa.")

        return WorkspaceUserView(
            user=user,
            membership=membership,
        )

    def update_member(
        self,
        workspace_public_id: str,
        user_public_id: str,
        payload: WorkspaceMembershipUpdate,
    ) -> WorkspaceUserView:
        workspace = self._workspace(workspace_public_id)
        self._lock_workspace(workspace.id)
        view = self.get_member(
            workspace_public_id,
            user_public_id,
        )
        self.db.refresh(view.membership)
        self.db.refresh(view.user)
        before_data = membership_snapshot(
            view.membership,
            user_public_id=view.user.public_id,
        )

        changes = payload.model_dump(exclude_unset=True)
        self._authorize_change(
            workspace.id,
            target=view.membership,
            role=changes.get("role"),
            active=changes.get("active"),
        )
        self._protect_last_admin(view, changes)

        if "role" in changes:
            view.membership.role = changes["role"]
        if "active" in changes:
            view.membership.active = changes["active"]

        self.memberships.save(view.membership)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="membership",
            entity_public_id=view.user.public_id,
            action="membership.updated",
            before_data=before_data,
            after_data=membership_snapshot(
                view.membership,
                user_public_id=view.user.public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(view.membership)
        return view

    def deactivate_member(
        self,
        workspace_public_id: str,
        user_public_id: str,
    ) -> WorkspaceUserView:
        workspace = self._workspace(workspace_public_id)
        self._lock_workspace(workspace.id)
        view = self.get_member(
            workspace_public_id,
            user_public_id,
        )
        self.db.refresh(view.membership)
        self.db.refresh(view.user)
        before_data = membership_snapshot(
            view.membership,
            user_public_id=view.user.public_id,
        )

        self._authorize_change(workspace.id, target=view.membership, active=False)
        self._protect_last_admin(view, {"active": False})
        view.membership.active = False
        self.memberships.save(view.membership)

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="membership",
            entity_public_id=view.user.public_id,
            action="membership.deactivated",
            before_data=before_data,
            after_data=membership_snapshot(
                view.membership,
                user_public_id=view.user.public_id,
            ),
        )

        self.db.commit()
        self.db.refresh(view.membership)
        return view

    def permissions(
        self,
        workspace_public_id: str,
        user_public_id: str,
    ) -> tuple[str, tuple[str, ...]]:
        view = self.get_member(
            workspace_public_id,
            user_public_id,
        )

        return (
            view.membership.role,
            get_permissions_for_role(view.membership.role),
        )

    def team_summary(self, workspace_public_id: str) -> dict[str, object]:
        workspace = self._workspace(workspace_public_id)
        member_rows = self.memberships.list_for_workspace(workspace.id)
        memberships = [membership for membership, _ in member_rows]

        leads = list(
            self.db.scalars(
                select(Lead).where(
                    Lead.workspace_id == workspace.id,
                    Lead.active.is_(True),
                )
            ).all()
        )
        opportunities = list(
            self.db.scalars(
                select(Opportunity).where(
                    Opportunity.workspace_id == workspace.id,
                )
            ).all()
        )
        activities = list(
            self.db.scalars(
                select(Activity).where(
                    Activity.workspace_id == workspace.id,
                )
            ).all()
        )

        now = datetime.now(timezone.utc)
        member_items: list[dict[str, object]] = []

        for membership, user in member_rows:
            assigned_leads = sum(
                lead.owner_membership_id == membership.id for lead in leads
            )
            member_opportunities = [
                opportunity
                for opportunity in opportunities
                if opportunity.owner_membership_id == membership.id
            ]
            open_opportunities = sum(
                opportunity.status == "open" for opportunity in member_opportunities
            )
            won_opportunities = sum(
                opportunity.status == "won" for opportunity in member_opportunities
            )
            lost_opportunities = sum(
                opportunity.status == "lost" for opportunity in member_opportunities
            )
            won_value = sum(
                (
                    opportunity.value_amount
                    for opportunity in member_opportunities
                    if opportunity.status == "won"
                ),
                start=Decimal("0.00"),
            )

            member_activities = [
                activity
                for activity in activities
                if activity.owner_membership_id == membership.id
            ]
            pending_activities = sum(
                activity.status == "pending" for activity in member_activities
            )
            overdue_activities = sum(
                activity.status == "pending"
                and self._as_utc(activity.due_at) is not None
                and self._as_utc(activity.due_at) < now
                for activity in member_activities
            )

            member_items.append(
                {
                    "public_id": user.public_id,
                    "name": user.name,
                    "email": user.email,
                    "user_active": user.active,
                    "role": membership.role,
                    "membership_active": membership.active,
                    "assigned_leads": assigned_leads,
                    "open_opportunities": open_opportunities,
                    "won_opportunities": won_opportunities,
                    "lost_opportunities": lost_opportunities,
                    "conversion_rate": self._conversion_rate(
                        won_opportunities,
                        lost_opportunities,
                    ),
                    "won_value": won_value,
                    "pending_activities": pending_activities,
                    "overdue_activities": overdue_activities,
                }
            )

        active_memberships = [
            (membership, user)
            for membership, user in member_rows
            if membership.active and user.active
        ]

        return {
            "workspace_public_id": workspace.public_id,
            "total_members": len(memberships),
            "active_members": len(active_memberships),
            "sellers": sum(
                membership.role == "seller" for membership, _ in active_memberships
            ),
            "managers": sum(
                membership.role in {"admin", "manager"}
                for membership, _ in active_memberships
            ),
            "operators": sum(
                membership.role == "operator" for membership, _ in active_memberships
            ),
            "total_assigned_leads": sum(
                int(item["assigned_leads"]) for item in member_items
            ),
            "total_open_opportunities": sum(
                int(item["open_opportunities"]) for item in member_items
            ),
            "total_won_value": sum(
                (Decimal(item["won_value"]) for item in member_items),
                start=Decimal("0.00"),
            ),
            "members": member_items,
        }
