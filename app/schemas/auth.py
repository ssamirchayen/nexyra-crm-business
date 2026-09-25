from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.security import PasswordStrengthError, validate_password_strength


class AuthLogin(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("E-mail inválido.")
        return normalized


class AuthChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        try:
            return validate_password_strength(value)
        except PasswordStrengthError as exc:
            raise ValueError(str(exc)) from exc


class AuthPasswordRecoveryRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("E-mail inválido.")
        return normalized


class AuthPasswordRecoveryReset(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        try:
            return validate_password_strength(value)
        except PasswordStrengthError as exc:
            raise ValueError(str(exc)) from exc


class AuthUserRead(BaseModel):
    public_id: str
    name: str
    email: str
    must_change_password: bool


class AuthWorkspaceRead(BaseModel):
    public_id: str
    name: str
    slug: str
    segment: str
    role: str
    permissions: list[str]


class AuthContextRead(BaseModel):
    user: AuthUserRead
    workspaces: list[AuthWorkspaceRead]


class AuthLoginRead(AuthContextRead):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AuthSessionRead(BaseModel):
    public_id: str
    current: bool
    ip_address: str | None
    user_agent: str | None
    expires_at: datetime
    revoked_at: datetime | None
    revoked_reason: str | None
    last_seen_at: datetime
    created_at: datetime


class AuthSessionsRevokedRead(BaseModel):
    ok: bool = True
    revoked: int
    message: str


class AuthPasswordRecoveryRequestedRead(BaseModel):
    ok: bool = True
    message: str
    expires_in_minutes: int


class AuthMessageRead(BaseModel):
    ok: bool = True
    message: str
