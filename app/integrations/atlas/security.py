from __future__ import annotations

from secrets import compare_digest

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.permissions import get_permissions_for_role
from app.repositories import (
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)


class AtlasIntegrationUnauthorizedError(ValueError):
    pass


class AtlasIntegrationForbiddenError(ValueError):
    pass


class AtlasIntegrationWorkspaceError(ValueError):
    pass


class AtlasIntegrationSecurity:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)

    def verify_token(self, supplied_token: str) -> None:
        expected = self.settings.atlas_integration_token
        if not supplied_token or not compare_digest(supplied_token, expected):
            raise AtlasIntegrationUnauthorizedError(
                "Token de integração inválido."
            )

    def authorize(
        self,
        *,
        workspace_public_id: str,
        actor_user_public_id: str,
        required_permission: str,
    ):
        workspace = self.workspaces.get_by_public_id(
            workspace_public_id
        )
        if workspace is None:
            raise AtlasIntegrationWorkspaceError(
                f"Empresa não encontrada: {workspace_public_id}"
            )

        user = self.users.get_by_public_id(actor_user_public_id)
        if user is None or not user.active:
            raise AtlasIntegrationForbiddenError(
                "Usuário de integração não encontrado ou inativo."
            )

        membership = self.memberships.get(
            workspace_id=workspace.id,
            user_id=user.id,
        )
        if membership is None or not membership.active:
            raise AtlasIntegrationForbiddenError(
                "Usuário não possui acesso ativo a esta empresa."
            )

        permissions = get_permissions_for_role(membership.role)
        if required_permission not in permissions:
            raise AtlasIntegrationForbiddenError(
                f"Permissão necessária: {required_permission}"
            )

        return workspace, user, membership, permissions
