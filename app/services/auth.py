from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuthSession, User, UserCredential, Workspace, WorkspaceMembership
from app.permissions import get_permissions_for_role
from app.repositories import (
    AuditRepository,
    AuthSessionRepository,
    PasswordResetRequestRepository,
    UserCredentialRepository,
    UserRepository,
    WorkspaceMembershipRepository,
)
from app.security import (
    hash_password,
    hash_password_reset_token,
    hash_session_token,
    new_password_reset_token,
    new_session_token,
    verify_password,
)


class InvalidCredentialsError(ValueError):
    pass


class AuthSessionInvalidError(ValueError):
    pass


class AuthAccessDisabledError(ValueError):
    pass


class AuthAccountLockedError(ValueError):
    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(1, retry_after_seconds)


class PasswordChangeError(ValueError):
    pass


class SessionManagementError(ValueError):
    pass


class PasswordRecoveryError(ValueError):
    pass


@dataclass(frozen=True)
class AuthWorkspaceAccess:
    membership: WorkspaceMembership
    workspace: Workspace


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    credential: UserCredential
    session: AuthSession
    workspaces: tuple[AuthWorkspaceAccess, ...]


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    context: AuthenticatedSession


@dataclass(frozen=True)
class PasswordRecoveryPreparation:
    """Token cru destinado exclusivamente ao futuro canal de entrega.

    A API pública ainda não expõe este valor. O banco persiste apenas o hash.
    """

    token: str
    expires_at: datetime


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.users = UserRepository(db)
        self.credentials = UserCredentialRepository(db)
        self.sessions = AuthSessionRepository(db)
        self.password_resets = PasswordResetRequestRepository(db)
        self.memberships = WorkspaceMembershipRepository(db)
        self.audit = AuditRepository(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _record_auth_event(
        self,
        *,
        user: User,
        action: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        for membership, workspace in self.memberships.list_for_user(user.id):
            if not membership.active or not workspace.active:
                continue
            self.audit.create(
                workspace_id=workspace.id,
                actor_membership_id=None,
                actor_type="system",
                entity_type="user",
                entity_public_id=user.public_id,
                action=action,
                metadata_json=dict(metadata or {}),
            )

    def _active_accesses(self, user_id: int) -> tuple[AuthWorkspaceAccess, ...]:
        return tuple(
            AuthWorkspaceAccess(membership=membership, workspace=workspace)
            for membership, workspace in self.memberships.list_for_user(user_id)
            if membership.active and workspace.active
        )

    def _build_context(
        self,
        *,
        user: User,
        credential: UserCredential,
        session: AuthSession,
    ) -> AuthenticatedSession:
        accesses = self._active_accesses(user.id)
        if not accesses:
            raise AuthAccessDisabledError("Usuário sem acesso ativo a nenhuma empresa.")
        return AuthenticatedSession(
            user=user,
            credential=credential,
            session=session,
            workspaces=accesses,
        )

    def _lockout_remaining(self, credential: UserCredential) -> int:
        if credential.locked_until is None:
            return 0

        now = self._now()
        locked_until = self._as_utc(credential.locked_until)
        if locked_until <= now:
            credential.failed_login_attempts = 0
            credential.locked_until = None
            credential.last_failed_login_at = None
            self.credentials.save(credential)
            self.db.commit()
            return 0

        return max(1, int((locked_until - now).total_seconds()))

    def _register_failed_login(self, credential: UserCredential) -> None:
        now = self._now()
        credential.failed_login_attempts += 1
        credential.last_failed_login_at = now

        if credential.failed_login_attempts >= self.settings.auth_login_max_attempts:
            credential.locked_until = now + timedelta(
                minutes=self.settings.auth_lockout_minutes
            )

        self.credentials.save(credential)
        self.db.commit()

    def _clear_failed_login_state(self, credential: UserCredential) -> None:
        if (
            credential.failed_login_attempts == 0
            and credential.locked_until is None
            and credential.last_failed_login_at is None
        ):
            return

        credential.failed_login_attempts = 0
        credential.locked_until = None
        credential.last_failed_login_at = None
        self.credentials.save(credential)

    def confirm_password(self, credential: UserCredential, password: str) -> None:
        """Reauthenticate sensitive actions using the login lockout policy."""
        self.db.refresh(credential, with_for_update=True)
        remaining = self._lockout_remaining(credential)
        if remaining:
            raise AuthAccountLockedError(
                "Muitas tentativas. Aguarde para confirmar sua senha novamente.",
                retry_after_seconds=remaining,
            )
        if not verify_password(password, credential.password_hash):
            self._register_failed_login(credential)
            remaining = self._lockout_remaining(credential)
            if remaining:
                raise AuthAccountLockedError(
                    "Muitas tentativas. Aguarde para confirmar sua senha novamente.",
                    retry_after_seconds=remaining,
                )
            raise InvalidCredentialsError("Sua senha atual está incorreta.")
        self._clear_failed_login_state(credential)

    def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResult:
        user = self.users.get_by_email(email)
        if user is None or not user.active:
            raise InvalidCredentialsError("E-mail ou senha inválidos.")

        credential = self.credentials.get_by_user_id(user.id)
        if credential is None:
            raise InvalidCredentialsError("E-mail ou senha inválidos.")

        self.db.refresh(credential, with_for_update=True)
        remaining = self._lockout_remaining(credential)
        if remaining:
            raise AuthAccountLockedError(
                "Muitas tentativas de acesso. Tente novamente mais tarde.",
                retry_after_seconds=remaining,
            )

        if not verify_password(password, credential.password_hash):
            self._register_failed_login(credential)
            remaining = self._lockout_remaining(credential)
            if remaining:
                raise AuthAccountLockedError(
                    "Muitas tentativas de acesso. Tente novamente mais tarde.",
                    retry_after_seconds=remaining,
                )
            raise InvalidCredentialsError("E-mail ou senha inválidos.")

        self._clear_failed_login_state(credential)

        if not self._active_accesses(user.id):
            self.db.commit()
            raise AuthAccessDisabledError("Usuário sem acesso ativo a nenhuma empresa.")

        token = new_session_token()
        expires_at = self._now() + timedelta(hours=self.settings.auth_session_hours)
        auth_session = self.sessions.create(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
            ip_address=(ip_address or None),
            user_agent=(user_agent or None),
        )
        self.db.commit()
        self.db.refresh(auth_session)

        return LoginResult(
            access_token=token,
            context=self._build_context(
                user=user,
                credential=credential,
                session=auth_session,
            ),
        )

    def authenticate(self, token: str) -> AuthenticatedSession:
        auth_session = self.sessions.get_by_token_hash(hash_session_token(token))
        if auth_session is None or auth_session.revoked_at is not None:
            raise AuthSessionInvalidError("Sessão inválida ou encerrada.")

        now = self._now()
        if self._as_utc(auth_session.expires_at) <= now:
            raise AuthSessionInvalidError("Sessão expirada.")

        user = self.users.get_by_id(auth_session.user_id)
        if user is None or not user.active:
            raise AuthSessionInvalidError("Sessão inválida ou encerrada.")

        credential = self.credentials.get_by_user_id(user.id)
        if credential is None:
            raise AuthSessionInvalidError("Sessão inválida ou encerrada.")

        last_seen = self._as_utc(auth_session.last_seen_at)
        touch_after = timedelta(minutes=self.settings.auth_session_touch_minutes)
        if now - last_seen >= touch_after:
            auth_session.last_seen_at = now
            self.sessions.save(auth_session)
            self.db.commit()
            self.db.refresh(auth_session)

        return self._build_context(
            user=user,
            credential=credential,
            session=auth_session,
        )

    def logout(self, context: AuthenticatedSession) -> None:
        if context.session.revoked_at is None:
            context.session.revoked_at = self._now()
            context.session.revoked_reason = "logout"
            self.sessions.save(context.session)
            self.db.commit()

    def list_sessions(self, context: AuthenticatedSession) -> list[AuthSession]:
        return self.sessions.list_for_user(context.user.id)

    def revoke_other_sessions(self, context: AuthenticatedSession) -> int:
        now = self._now()
        revoked = 0
        for auth_session in self.sessions.list_for_user(context.user.id):
            if (
                auth_session.id == context.session.id
                or auth_session.revoked_at is not None
            ):
                continue
            auth_session.revoked_at = now
            auth_session.revoked_reason = "revoked_by_user"
            self.sessions.save(auth_session)
            revoked += 1
        self.db.commit()
        return revoked

    def revoke_session(
        self,
        context: AuthenticatedSession,
        *,
        session_public_id: str,
    ) -> None:
        target = self.sessions.get_for_user_by_public_id(
            user_id=context.user.id,
            public_id=session_public_id,
        )
        if target is None:
            raise SessionManagementError("Sessão não encontrada.")
        if target.id == context.session.id:
            raise SessionManagementError(
                "Use 'Sair do CRM' para encerrar a sessão atual."
            )
        if target.revoked_at is None:
            target.revoked_at = self._now()
            target.revoked_reason = "revoked_by_user"
            self.sessions.save(target)
            self.db.commit()

    def change_password(
        self,
        context: AuthenticatedSession,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        credential = context.credential
        if not verify_password(current_password, credential.password_hash):
            raise PasswordChangeError("Senha atual incorreta.")

        if verify_password(new_password, credential.password_hash):
            raise PasswordChangeError("A nova senha deve ser diferente da senha atual.")

        now = self._now()
        credential.password_hash = hash_password(
            new_password,
            iterations=self.settings.auth_password_iterations,
        )
        credential.must_change_password = False
        credential.password_updated_at = now
        credential.failed_login_attempts = 0
        credential.locked_until = None
        credential.last_failed_login_at = None
        self.credentials.save(credential)

        for auth_session in self.sessions.list_for_user(context.user.id):
            if auth_session.revoked_at is None:
                auth_session.revoked_at = now
                auth_session.revoked_reason = "password_changed"
                self.sessions.save(auth_session)

        self.db.commit()

    def configure_password(
        self,
        *,
        user: User,
        password: str,
        must_change_password: bool = False,
    ) -> UserCredential:
        credential = self.credentials.get_by_user_id(user.id)
        encoded = hash_password(
            password,
            iterations=self.settings.auth_password_iterations,
        )
        now = self._now()

        if credential is None:
            credential = self.credentials.create(
                user_id=user.id,
                password_hash=encoded,
                must_change_password=must_change_password,
            )
        else:
            credential.password_hash = encoded
            credential.must_change_password = must_change_password
            credential.password_updated_at = now
            credential.failed_login_attempts = 0
            credential.locked_until = None
            credential.last_failed_login_at = None
            self.credentials.save(credential)

        for auth_session in self.sessions.list_for_user(user.id):
            if auth_session.revoked_at is None:
                auth_session.revoked_at = now
                auth_session.revoked_reason = "password_reconfigured"
                self.sessions.save(auth_session)

        self.db.commit()
        self.db.refresh(credential)
        return credential

    def prepare_password_recovery(
        self,
        *,
        email: str,
    ) -> PasswordRecoveryPreparation | None:
        """Cria um token de uso único sem expor existência da conta.

        O chamador público deve sempre responder de forma genérica. O token cru
        existe apenas em memória para ser entregue pelo canal configurado; o banco
        persiste somente SHA-256. Solicitações repetidas em um intervalo curto não
        invalidam o link recém-emitido.
        """

        user = self.users.get_by_email(email)
        if user is None or not user.active:
            return None
        if self.credentials.get_by_user_id(user.id) is None:
            return None

        now = self._now()
        existing = self.password_resets.list_for_user(user.id)
        if existing:
            latest = existing[0]
            created_at = self._as_utc(latest.created_at)
            cooldown = timedelta(
                seconds=self.settings.auth_password_reset_cooldown_seconds
            )
            if now - created_at < cooldown:
                return None

        for request in existing:
            if request.used_at is None and request.revoked_at is None:
                request.revoked_at = now
                self.password_resets.save(request)

        token = new_password_reset_token()
        expires_at = now + timedelta(minutes=self.settings.auth_password_reset_minutes)
        self.password_resets.create(
            user_id=user.id,
            token_hash=hash_password_reset_token(token),
            expires_at=expires_at,
        )
        self._record_auth_event(
            user=user,
            action="auth.password_recovery.requested",
            metadata={
                "expires_in_minutes": self.settings.auth_password_reset_minutes,
            },
        )
        self.db.commit()
        return PasswordRecoveryPreparation(token=token, expires_at=expires_at)

    def reset_password_with_token(
        self,
        *,
        token: str,
        new_password: str,
    ) -> None:
        request = self.password_resets.get_by_token_hash(
            hash_password_reset_token(token)
        )
        invalid_message = "Link de recuperação inválido ou expirado."
        if request is None:
            raise PasswordRecoveryError(invalid_message)

        now = self._now()
        if request.used_at is not None or request.revoked_at is not None:
            raise PasswordRecoveryError(invalid_message)
        if self._as_utc(request.expires_at) <= now:
            request.revoked_at = now
            self.password_resets.save(request)
            self.db.commit()
            raise PasswordRecoveryError(invalid_message)

        user = self.users.get_by_id(request.user_id)
        if user is None or not user.active:
            request.revoked_at = now
            self.password_resets.save(request)
            self.db.commit()
            raise PasswordRecoveryError(invalid_message)

        credential = self.credentials.get_by_user_id(user.id)
        if credential is None:
            request.revoked_at = now
            self.password_resets.save(request)
            self.db.commit()
            raise PasswordRecoveryError(invalid_message)

        if verify_password(new_password, credential.password_hash):
            raise PasswordRecoveryError(
                "A nova senha deve ser diferente da senha anterior."
            )

        credential.password_hash = hash_password(
            new_password,
            iterations=self.settings.auth_password_iterations,
        )
        credential.must_change_password = False
        credential.password_updated_at = now
        credential.failed_login_attempts = 0
        credential.locked_until = None
        credential.last_failed_login_at = None
        self.credentials.save(credential)

        request.used_at = now
        self.password_resets.save(request)
        for other_request in self.password_resets.list_for_user(user.id):
            if other_request.id == request.id:
                continue
            if other_request.used_at is None and other_request.revoked_at is None:
                other_request.revoked_at = now
                self.password_resets.save(other_request)

        for auth_session in self.sessions.list_for_user(user.id):
            if auth_session.revoked_at is None:
                auth_session.revoked_at = now
                auth_session.revoked_reason = "password_reset"
                self.sessions.save(auth_session)

        self._record_auth_event(
            user=user,
            action="auth.password_recovery.completed",
            metadata={"sessions_revoked": True},
        )
        self.db.commit()

    @staticmethod
    def permissions_for(access: AuthWorkspaceAccess) -> list[str]:
        return list(get_permissions_for_role(access.membership.role))
