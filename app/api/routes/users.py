from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AppSecurity,
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.models import (
    AuthSession,
    PasswordResetRequest,
    User,
    UserCredential,
    Workspace,
    WorkspaceMembership,
)
from app.permissions import ROLE_PERMISSIONS
from app.schemas import (
    PermissionsRead,
    RoleRead,
    TeamSummaryRead,
    WorkspaceMembershipUpdate,
    WorkspaceUserCreate,
    WorkspaceUserRead,
)
from app.schemas.auth import AuthMessageRead, AuthSessionRead
from app.schemas.user import AdminPasswordResetCreate, AdminPasswordResetRead
from app.security import hash_password
from app.services import (
    MembershipConflictError,
    MembershipNotFoundError,
    UserNotFoundError,
    WorkspaceNotFoundError,
    WorkspaceUserService,
)
from app.services.audit import AuditService
from app.services.auth import (
    AuthAccountLockedError,
    AuthService,
    InvalidCredentialsError,
)
from app.services.user import MembershipPermissionError

router = APIRouter(tags=["users"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadMembers = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("members.read")),
]
CanCreateMembers = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("members.create")),
]
CanUpdateMembers = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("members.update")),
]
CanDeactivateMembers = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("members.deactivate")),
]


def _serialize_member(view) -> WorkspaceUserRead:
    return WorkspaceUserRead(
        public_id=view.user.public_id,
        name=view.user.name,
        email=view.user.email,
        user_active=view.user.active,
        role=view.membership.role,
        membership_active=view.membership.active,
    )


def _translate_error(exc: ValueError) -> None:
    if isinstance(
        exc,
        (WorkspaceNotFoundError, UserNotFoundError, MembershipNotFoundError),
    ):
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if isinstance(exc, MembershipPermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if isinstance(exc, MembershipConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    raise exc


@router.get("/roles", response_model=list[RoleRead])
def list_roles(_security: AppSecurity) -> list[RoleRead]:
    return [
        RoleRead(role=role, permissions=list(permissions))
        for role, permissions in ROLE_PERMISSIONS.items()
    ]


@router.post(
    "/workspaces/{workspace_public_id}/members",
    response_model=WorkspaceUserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_member(
    workspace_public_id: str,
    payload: WorkspaceUserCreate,
    db: DbSession,
    _authorization: CanCreateMembers,
) -> WorkspaceUserRead:
    try:
        view = WorkspaceUserService(db).create_member(
            workspace_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _serialize_member(view)


@router.get(
    "/workspaces/{workspace_public_id}/members",
    response_model=list[WorkspaceUserRead],
)
def list_members(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadMembers,
) -> list[WorkspaceUserRead]:
    try:
        views = WorkspaceUserService(db).list_members(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [_serialize_member(view) for view in views]


@router.get(
    "/workspaces/{workspace_public_id}/team/summary",
    response_model=TeamSummaryRead,
)
def team_summary(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadMembers,
) -> TeamSummaryRead:
    try:
        summary = WorkspaceUserService(db).team_summary(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise
    return TeamSummaryRead(**summary)


@router.get(
    "/workspaces/{workspace_public_id}/members/{user_public_id}",
    response_model=WorkspaceUserRead,
)
def get_member(
    workspace_public_id: str,
    user_public_id: str,
    db: DbSession,
    _authorization: CanReadMembers,
) -> WorkspaceUserRead:
    try:
        view = WorkspaceUserService(db).get_member(
            workspace_public_id,
            user_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _serialize_member(view)


@router.patch(
    "/workspaces/{workspace_public_id}/members/{user_public_id}",
    response_model=WorkspaceUserRead,
)
def update_member(
    workspace_public_id: str,
    user_public_id: str,
    payload: WorkspaceMembershipUpdate,
    db: DbSession,
    _authorization: CanUpdateMembers,
) -> WorkspaceUserRead:
    try:
        view = WorkspaceUserService(db).update_member(
            workspace_public_id,
            user_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _serialize_member(view)


@router.post(
    "/workspaces/{workspace_public_id}/members/{user_public_id}/deactivate",
    response_model=WorkspaceUserRead,
)
def deactivate_member(
    workspace_public_id: str,
    user_public_id: str,
    db: DbSession,
    _authorization: CanDeactivateMembers,
) -> WorkspaceUserRead:
    try:
        view = WorkspaceUserService(db).deactivate_member(
            workspace_public_id,
            user_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return _serialize_member(view)


@router.get(
    "/workspaces/{workspace_public_id}/members/{user_public_id}/permissions",
    response_model=PermissionsRead,
)
def get_member_permissions(
    workspace_public_id: str,
    user_public_id: str,
    db: DbSession,
    _authorization: CanReadMembers,
) -> PermissionsRead:
    try:
        role, permissions = WorkspaceUserService(db).permissions(
            workspace_public_id,
            user_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return PermissionsRead(
        workspace_public_id=workspace_public_id,
        user_public_id=user_public_id,
        role=role,
        permissions=list(permissions),
    )


CanManageSessions = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("sessions.manage")),
]


def _session_target(
    db: Session,
    authorization: WorkspaceAuthorization,
    user_public_id: str,
) -> User:
    # Sessions are global. Never expose or revoke a different company's access.
    if authorization.auth is None or authorization.access is None:
        raise HTTPException(401, "Entre com uma conta administrativa.")
    workspace_id = authorization.access.workspace.id
    user = db.scalar(
        select(User)
        .join(WorkspaceMembership)
        .where(
            User.public_id == user_public_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if user is None:
        raise HTTPException(404, "Membro não encontrado.")
    other = db.scalar(
        select(WorkspaceMembership.id)
        .where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.workspace_id != workspace_id,
        )
        .limit(1)
    )
    if other is not None:
        raise HTTPException(
            409,
            "Esta conta possui vínculos com outras empresas. "
            "O próprio usuário deve gerenciar suas sessões na área de segurança.",
        )
    return user


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.get(
    "/workspaces/{workspace_public_id}/members/{user_public_id}/sessions",
    response_model=list[AuthSessionRead],
)
def list_member_sessions(
    workspace_public_id: str,
    user_public_id: str,
    db: DbSession,
    authorization: CanManageSessions,
) -> list[AuthSessionRead]:
    user = _session_target(db, authorization, user_public_id)
    sessions = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
        .order_by(AuthSession.created_at.desc(), AuthSession.id.desc())
        .limit(100)
    ).all()
    return [
        AuthSessionRead(
            public_id=item.public_id,
            current=item.id == authorization.auth.session.id,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            expires_at=_utc(item.expires_at),
            revoked_at=None,
            revoked_reason=None,
            last_seen_at=_utc(item.last_seen_at),
            created_at=_utc(item.created_at),
        )
        for item in sessions
    ]


@router.post(
    "/workspaces/{workspace_public_id}/members/{user_public_id}/sessions/{session_public_id}/revoke",
    response_model=AuthMessageRead,
)
def revoke_member_session(
    workspace_public_id: str,
    user_public_id: str,
    session_public_id: str,
    db: DbSession,
    authorization: CanManageSessions,
) -> AuthMessageRead:
    user = _session_target(db, authorization, user_public_id)
    target = db.scalar(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.public_id == session_public_id,
        )
    )
    if target is None:
        raise HTTPException(404, "Sessão não encontrada.")
    if target.id == authorization.auth.session.id:
        raise HTTPException(409, "Use 'Sair do CRM' para encerrar a sessão atual.")
    now = datetime.now(UTC)
    changed = db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == target.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .values(revoked_at=now, revoked_reason="revoked_by_admin")
        .execution_options(synchronize_session="fetch")
    )
    if changed.rowcount:
        AuditService(db).record(
            workspace_id=authorization.access.workspace.id,
            entity_type="auth_session",
            entity_public_id=session_public_id,
            action="session.revoked_by_admin",
            metadata={"user_public_id": user_public_id},
        )
    db.commit()
    return AuthMessageRead(message="Sessão encerrada ou já inativa.")


CanResetPasswords = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("members.reset_password")),
]


@router.post(
    "/workspaces/{workspace_public_id}/members/{user_public_id}/reset-password",
    response_model=AdminPasswordResetRead,
)
def reset_member_password(
    workspace_public_id: str,
    user_public_id: str,
    payload: AdminPasswordResetCreate,
    response: Response,
    db: DbSession,
    authorization: CanResetPasswords,
) -> AdminPasswordResetRead:
    if authorization.auth is None or authorization.access is None:
        raise HTTPException(401, "Entre com uma conta administrativa.")
    auth = authorization.auth
    workspace_id = authorization.access.workspace.id
    db.execute(
        select(Workspace.id).where(Workspace.id == workspace_id).with_for_update()
    ).scalar_one()
    db.refresh(authorization.access.membership)
    db.refresh(auth.session)
    db.refresh(auth.credential)
    if (
        not authorization.access.membership.active
        or authorization.access.membership.role != "admin"
        or auth.session.revoked_at is not None
        or auth.credential.must_change_password
    ):
        raise HTTPException(403, "Seu acesso não permite redefinir senhas.")
    if user_public_id == auth.user.public_id:
        raise HTTPException(409, "Altere sua própria senha na área de Segurança.")

    target = db.scalar(
        select(User)
        .join(WorkspaceMembership)
        .where(
            User.public_id == user_public_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if target is None:
        raise HTTPException(404, "Membro não encontrado.")
    db.refresh(target, with_for_update={"key_share": True})
    membership = db.scalar(
        select(WorkspaceMembership)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == target.id,
        )
        .execution_options(populate_existing=True)
    )
    if not target.active or not membership.active:
        raise HTTPException(409, "Reative o membro antes de redefinir sua senha.")
    if (
        db.scalar(
            select(WorkspaceMembership.id)
            .where(
                WorkspaceMembership.user_id == target.id,
                WorkspaceMembership.workspace_id != workspace_id,
            )
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(
            409,
            "Esta conta possui vínculos com outras empresas. "
            "Use o procedimento de recuperação do titular da conta.",
        )

    service = AuthService(db)
    try:
        service.confirm_password(
            auth.credential, payload.current_password.get_secret_value()
        )
    except AuthAccountLockedError as exc:
        raise HTTPException(
            429, str(exc), headers={"Retry-After": str(exc.retry_after_seconds)}
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(403, str(exc)) from exc

    now = datetime.now(UTC)
    temporary = "Aa1!" + secrets.token_urlsafe(24)
    credential = db.scalar(
        select(UserCredential)
        .where(
            UserCredential.user_id == target.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if credential is None:
        credential = UserCredential(user_id=target.id)
        db.add(credential)
    credential.password_hash = hash_password(
        temporary,
        iterations=service.settings.auth_password_iterations,
    )
    credential.must_change_password = True
    credential.password_updated_at = now
    credential.failed_login_attempts = 0
    credential.last_failed_login_at = None
    credential.locked_until = None
    # Bulk updates intentionally cover every session, not the inventory's limit.
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == target.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoked_reason="password_reset_by_admin")
        .execution_options(synchronize_session="fetch")
    )
    db.execute(
        update(PasswordResetRequest)
        .where(
            PasswordResetRequest.user_id == target.id,
            PasswordResetRequest.used_at.is_(None),
            PasswordResetRequest.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .execution_options(synchronize_session="fetch")
    )
    AuditService(db).record(
        workspace_id=workspace_id,
        entity_type="user",
        entity_public_id=user_public_id,
        action="user.password_reset_by_admin",
        metadata={"must_change_password": True},
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return AdminPasswordResetRead(
        temporary_password=temporary,
        message="Senha temporária gerada. Entregue-a ao titular por um canal seguro. "
        "A troca será obrigatória no próximo acesso.",
    )
