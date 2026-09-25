from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserCredential


class UserCredentialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def exists(self) -> bool:
        statement = select(UserCredential.id).limit(1)
        return self.db.scalar(statement) is not None

    def get_by_user_id(self, user_id: int) -> UserCredential | None:
        return self.db.scalar(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )

    def create(
        self,
        *,
        user_id: int,
        password_hash: str,
        must_change_password: bool = False,
    ) -> UserCredential:
        credential = UserCredential(
            user_id=user_id,
            password_hash=password_hash,
            must_change_password=must_change_password,
        )
        self.db.add(credential)
        self.db.flush()
        return credential

    def save(self, credential: UserCredential) -> UserCredential:
        self.db.add(credential)
        self.db.flush()
        return credential
