from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from app.permissions import VALID_ROLES
from app.security import PasswordStrengthError, validate_password_strength


class WorkspaceUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=255)
    role: str = Field(default="seller", min_length=2, max_length=30)
    initial_password: str | None = Field(default=None, min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
        ):
            raise ValueError("E-mail inválido.")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_ROLES:
            raise ValueError("Papel inválido. Use admin, manager, seller ou operator.")
        return normalized

    @field_validator("initial_password")
    @classmethod
    def validate_initial_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return validate_password_strength(value)
        except PasswordStrengthError as exc:
            raise ValueError(str(exc)) from exc


class WorkspaceMembershipUpdate(BaseModel):
    role: str | None = Field(default=None, min_length=2, max_length=30)
    active: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_null(self):
        for field in ("role", "active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"O campo {field} não pode ser nulo.")
        return self

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in VALID_ROLES:
            raise ValueError("Papel inválido. Use admin, manager, seller ou operator.")
        return normalized


class WorkspaceUserRead(BaseModel):
    public_id: str
    name: str
    email: str
    user_active: bool
    role: str
    membership_active: bool


class RoleRead(BaseModel):
    role: str
    permissions: list[str]


class PermissionsRead(BaseModel):
    workspace_public_id: str
    user_public_id: str
    role: str
    permissions: list[str]


class TeamMemberPerformanceRead(BaseModel):
    public_id: str
    name: str
    email: str
    user_active: bool
    role: str
    membership_active: bool
    assigned_leads: int
    open_opportunities: int
    won_opportunities: int
    lost_opportunities: int
    conversion_rate: float
    won_value: Decimal
    pending_activities: int
    overdue_activities: int


class TeamSummaryRead(BaseModel):
    workspace_public_id: str
    total_members: int
    active_members: int
    sellers: int
    managers: int
    operators: int
    total_assigned_leads: int
    total_open_opportunities: int
    total_won_value: Decimal
    members: list[TeamMemberPerformanceRead]


class AdminPasswordResetCreate(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)


class AdminPasswordResetRead(BaseModel):
    temporary_password: str
    must_change_password: bool = True
    message: str
