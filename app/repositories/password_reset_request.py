from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PasswordResetRequest


class PasswordResetRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetRequest:
        request = PasswordResetRequest(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(request)
        self.db.flush()
        return request

    def get_by_token_hash(self, token_hash: str) -> PasswordResetRequest | None:
        return self.db.scalar(
            select(PasswordResetRequest).where(
                PasswordResetRequest.token_hash == token_hash
            )
        )

    def list_for_user(self, user_id: int) -> list[PasswordResetRequest]:
        return list(
            self.db.scalars(
                select(PasswordResetRequest)
                .where(PasswordResetRequest.user_id == user_id)
                .order_by(PasswordResetRequest.created_at.desc())
            ).all()
        )

    def save(self, request: PasswordResetRequest) -> PasswordResetRequest:
        self.db.add(request)
        self.db.flush()
        return request
