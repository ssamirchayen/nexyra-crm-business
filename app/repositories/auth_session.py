from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuthSession


class AuthSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )

    def get_for_user_by_public_id(
        self,
        *,
        user_id: int,
        public_id: str,
    ) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.public_id == public_id,
            )
        )

    def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def list_for_user(self, user_id: int) -> list[AuthSession]:
        return list(
            self.db.scalars(
                select(AuthSession)
                .where(AuthSession.user_id == user_id)
                .order_by(AuthSession.created_at.desc())
                .limit(20)
            ).all()
        )

    def save(self, session: AuthSession) -> AuthSession:
        self.db.add(session)
        self.db.flush()
        return session
