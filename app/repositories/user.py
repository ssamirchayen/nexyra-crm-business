from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_public_id(self, public_id: str) -> User | None:
        return self.db.scalar(select(User).where(User.public_id == public_id))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def create(self, *, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self.db.add(user)
        self.db.flush()
        return user
