from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.lead import VALID_PRIORITIES

OwnerMode = Literal["keep", "assign", "clear"]


class LeadBatchRequest(BaseModel):
    lead_public_ids: list[str] = Field(min_length=1, max_length=100)
    status: str | None = Field(default=None, max_length=80)
    priority: str | None = Field(default=None, max_length=20)
    owner_mode: OwnerMode = "keep"
    owner_user_public_id: str | None = None
    active: bool | None = None
    dry_run: bool = True

    @field_validator("lead_public_ids")
    @classmethod
    def normalize_lead_ids(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in result:
                result.append(item)
        if not result:
            raise ValueError("Selecione ao menos um lead.")
        return result

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "_")
        return normalized or None

    @field_validator("priority")
    @classmethod
    def normalize_priority(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "_")
        if normalized not in VALID_PRIORITIES:
            raise ValueError("Prioridade inválida.")
        return normalized

    @model_validator(mode="after")
    def validate_operation(self) -> LeadBatchRequest:
        if self.owner_mode == "assign" and not self.owner_user_public_id:
            raise ValueError("Selecione o responsável da operação em lote.")
        if self.owner_mode != "assign" and self.owner_user_public_id is not None:
            raise ValueError(
                "owner_user_public_id só pode ser usado com owner_mode=assign."
            )
        if not any(
            (
                self.status is not None,
                self.priority is not None,
                self.owner_mode != "keep",
                self.active is not None,
            )
        ):
            raise ValueError("Defina ao menos uma alteração para a triagem em lote.")
        return self


class LeadBatchItemRead(BaseModel):
    lead_public_id: str
    lead_name: str
    changed: bool
    changed_fields: list[str]
    before_status: str
    after_status: str
    before_priority: str
    after_priority: str
    before_owner_user_public_id: str | None
    after_owner_user_public_id: str | None
    before_active: bool
    after_active: bool


class LeadBatchResultRead(BaseModel):
    dry_run: bool
    requested: int
    found: int
    changed: int
    unchanged: int
    items: list[LeadBatchItemRead]
