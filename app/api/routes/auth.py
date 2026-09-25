from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentAuth
from app.core.config import get_settings
from app.db import get_db
from app.schemas import (
    AuthChangePassword,
    AuthContextRead,
    AuthLogin,
    AuthLoginRead,
    AuthMessageRead,
    AuthPasswordRecoveryRequest,
    AuthPasswordRecoveryRequestedRead,
    AuthPasswordRecoveryReset,
    AuthSessionRead,
    AuthSessionsRevokedRead,
    AuthUserRead,
    AuthWorkspaceRead,
)
from app.security import PasswordResetDeliveryError, deliver_password_reset
from app.services.auth import (
    AuthAccessDisabledError,
    AuthAccountLockedError,
    AuthenticatedSession,
    AuthService,
    InvalidCredentialsError,
    PasswordChangeError,
    PasswordRecoveryError,
    SessionManagementError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
DbSession = Annotated[Session, Depends(get_db)]


def _context_read(context: AuthenticatedSession) -> AuthContextRead:
    service_permissions = AuthService.permissions_for
    return AuthContextRead(
        user=AuthUserRead(
            public_id=context.user.public_id,
            name=context.user.name,
            email=context.user.email,
            must_change_password=context.credential.must_change_password,
        ),
        workspaces=[
            AuthWorkspaceRead(
                public_id=access.workspace.public_id,
                name=access.workspace.name,
                slug=access.workspace.slug,
                segment=access.workspace.segment,
                role=access.membership.role,
                permissions=service_permissions(access),
            )
            for access in context.workspaces
        ],
    )


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host[:64]


@router.post("/login", response_model=AuthLoginRead)
def login(payload: AuthLogin, request: Request, db: DbSession) -> AuthLoginRead:
    try:
        result = AuthService(db).login(
            email=payload.email,
            password=payload.password,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent", "")[:512] or None,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthAccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except AuthAccessDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    context = _context_read(result.context)
    return AuthLoginRead(
        access_token=result.access_token,
        expires_at=result.context.session.expires_at,
        user=context.user,
        workspaces=context.workspaces,
    )


@router.get("/me", response_model=AuthContextRead)
def me(current: CurrentAuth) -> AuthContextRead:
    return _context_read(current)


@router.get("/sessions", response_model=list[AuthSessionRead])
def list_sessions(current: CurrentAuth, db: DbSession) -> list[AuthSessionRead]:
    return [
        AuthSessionRead(
            public_id=item.public_id,
            current=item.id == current.session.id,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            expires_at=item.expires_at,
            revoked_at=item.revoked_at,
            revoked_reason=item.revoked_reason,
            last_seen_at=item.last_seen_at,
            created_at=item.created_at,
        )
        for item in AuthService(db).list_sessions(current)
    ]


@router.post("/sessions/revoke-others", response_model=AuthSessionsRevokedRead)
def revoke_other_sessions(
    current: CurrentAuth,
    db: DbSession,
) -> AuthSessionsRevokedRead:
    revoked = AuthService(db).revoke_other_sessions(current)
    return AuthSessionsRevokedRead(
        revoked=revoked,
        message=(
            f"{revoked} outra(s) sessão(ões) encerrada(s)."
            if revoked
            else "Nenhuma outra sessão ativa para encerrar."
        ),
    )


@router.post(
    "/sessions/{session_public_id}/revoke",
    response_model=AuthMessageRead,
)
def revoke_session(
    session_public_id: str,
    current: CurrentAuth,
    db: DbSession,
) -> AuthMessageRead:
    try:
        AuthService(db).revoke_session(
            current,
            session_public_id=session_public_id,
        )
    except SessionManagementError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return AuthMessageRead(message="Sessão encerrada com sucesso.")


@router.post(
    "/password-recovery/request",
    response_model=AuthPasswordRecoveryRequestedRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_recovery(
    payload: AuthPasswordRecoveryRequest,
    db: DbSession,
) -> AuthPasswordRecoveryRequestedRead:
    settings = get_settings()
    prepared = AuthService(db).prepare_password_recovery(email=payload.email)
    if prepared is not None:
        try:
            deliver_password_reset(
                email=payload.email,
                token=prepared.token,
                settings=settings,
            )
        except PasswordResetDeliveryError:
            logger.exception(
                "Falha ao entregar recuperação de senha do Nexyra CRM."
            )

    return AuthPasswordRecoveryRequestedRead(
        message=(
            "Se o e-mail estiver cadastrado, você receberá as instruções "
            "para redefinir a senha."
        ),
        expires_in_minutes=settings.auth_password_reset_minutes,
    )


@router.post(
    "/password-recovery/reset",
    response_model=AuthMessageRead,
)
def reset_password(
    payload: AuthPasswordRecoveryReset,
    db: DbSession,
) -> AuthMessageRead:
    try:
        AuthService(db).reset_password_with_token(
            token=payload.token,
            new_password=payload.new_password,
        )
    except PasswordRecoveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return AuthMessageRead(
        message=(
            "Senha redefinida com sucesso. Todas as sessões anteriores foram "
            "encerradas; entre novamente."
        )
    )


@router.post("/logout", response_model=AuthMessageRead)
def logout(current: CurrentAuth, db: DbSession) -> AuthMessageRead:
    AuthService(db).logout(current)
    return AuthMessageRead(message="Sessão encerrada com sucesso.")


@router.post("/change-password", response_model=AuthMessageRead)
def change_password(
    payload: AuthChangePassword,
    current: CurrentAuth,
    db: DbSession,
) -> AuthMessageRead:
    try:
        AuthService(db).change_password(
            current,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except PasswordChangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return AuthMessageRead(
        message=(
            "Senha alterada. Todas as sessões foram encerradas; "
            "faça login novamente."
        )
    )
