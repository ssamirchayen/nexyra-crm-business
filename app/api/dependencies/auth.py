from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.permissions import get_permissions_for_role
from app.repositories import UserCredentialRepository
from app.services.auth import (
    AuthAccessDisabledError,
    AuthenticatedSession,
    AuthService,
    AuthSessionInvalidError,
    AuthWorkspaceAccess,
)

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
AuthHeader = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


@dataclass(frozen=True)
class AppSecurityContext:
    auth: AuthenticatedSession | None
    bootstrap: bool = False

    @property
    def user_public_id(self) -> str | None:
        return self.auth.user.public_id if self.auth is not None else None


@dataclass(frozen=True)
class WorkspaceAuthorization:
    auth: AuthenticatedSession | None
    access: AuthWorkspaceAccess | None
    permissions: frozenset[str]
    bootstrap: bool = False

    @property
    def user_public_id(self) -> str | None:
        return self.auth.user.public_id if self.auth is not None else None

    @property
    def membership_id(self) -> int | None:
        return self.access.membership.id if self.access is not None else None

    def has_permission(self, permission: str) -> bool:
        return self.bootstrap or permission in self.permissions


class WorkspacePermissionDependency:
    def __init__(self, permission: str) -> None:
        self.permission = permission

    def __call__(
        self,
        request: Request,
        db: DbSession,
        security: AppSecurity,
    ) -> WorkspaceAuthorization:
        workspace_public_id = (
            request.path_params.get("workspace_public_id")
            or request.path_params.get("public_id")
        )
        if not workspace_public_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rota protegida sem identificador de empresa.",
            )

        if security.bootstrap:
            _set_audit_context(db, None)
            return WorkspaceAuthorization(
                auth=None,
                access=None,
                permissions=frozenset(),
                bootstrap=True,
            )

        assert security.auth is not None
        access = next(
            (
                item
                for item in security.auth.workspaces
                if item.workspace.public_id == workspace_public_id
            ),
            None,
        )
        if access is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não possui acesso ativo a esta empresa.",
            )

        permissions = frozenset(get_permissions_for_role(access.membership.role))
        if self.permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão necessária: {self.permission}.",
            )

        _set_audit_context(db, access.membership.id)
        return WorkspaceAuthorization(
            auth=security.auth,
            access=access,
            permissions=permissions,
        )


def _set_audit_context(db: Session, membership_id: int | None) -> None:
    if membership_id is None:
        db.info.pop("audit_actor_type", None)
        db.info.pop("audit_actor_membership_id", None)
        return

    db.info["audit_actor_type"] = "user"
    db.info["audit_actor_membership_id"] = membership_id


def _raise_unauthorized(message: str = "Autenticação necessária.") -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authenticate_token(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> AuthenticatedSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        _raise_unauthorized()

    try:
        return AuthService(db).authenticate(credentials.credentials)
    except (AuthSessionInvalidError, AuthAccessDisabledError) as exc:
        _raise_unauthorized(str(exc))
        raise AssertionError("unreachable") from exc


def get_current_auth(
    credentials: AuthHeader,
    db: DbSession,
) -> AuthenticatedSession:
    return _authenticate_token(credentials, db)


CurrentAuth = Annotated[AuthenticatedSession, Depends(get_current_auth)]


def get_app_security(
    credentials: AuthHeader,
    db: DbSession,
) -> AppSecurityContext:
    # First-run / migration bootstrap: while no password credential exists,
    # the CRM remains accessible so the first administrator can be configured.
    # As soon as the first credential is stored, every protected API requires
    # a valid bearer session.
    if not UserCredentialRepository(db).exists():
        return AppSecurityContext(auth=None, bootstrap=True)

    auth = _authenticate_token(credentials, db)
    if auth.credential.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Troca de senha obrigatória antes de acessar o CRM.",
        )
    return AppSecurityContext(auth=auth)


AppSecurity = Annotated[AppSecurityContext, Depends(get_app_security)]


def require_workspace_permission(permission: str) -> Callable[..., WorkspaceAuthorization]:
    return WorkspacePermissionDependency(permission)


def ensure_permission(
    authorization: WorkspaceAuthorization,
    permission: str,
) -> None:
    if not authorization.has_permission(permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permissão necessária: {permission}.",
        )


def ensure_can_assign_user(
    authorization: WorkspaceAuthorization,
    target_user_public_id: str | None,
) -> None:
    if authorization.bootstrap:
        return

    if target_user_public_id is not None and target_user_public_id == authorization.user_public_id:
        return

    ensure_permission(authorization, "leads.assign")
