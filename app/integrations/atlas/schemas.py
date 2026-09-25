from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.integrations.atlas.contract import SUPPORTED_ATLAS_ACTIONS


class AtlasHealthRead(BaseModel):
    ok: bool
    product: str
    crm_version: str
    contract_name: str
    contract_version: str


class AtlasCapabilitiesRead(BaseModel):
    contract_name: str
    contract_version: str
    capabilities: list[str]
    supported_actions: list[str]
    confirmation_required_for_execution: bool
    supported_actor_types: list[str]


class AtlasWorkspaceContextRead(BaseModel):
    contract_version: str
    workspace: dict[str, object]
    segment: dict[str, object]
    actor: dict[str, object]
    members: list[dict[str, object]]
    counts: dict[str, int]
    opportunity_metrics: dict[str, object]
    lead_sources: list[dict[str, object]]
    pending_followups: list[dict[str, object]]


class AtlasActionRequest(BaseModel):
    action: str = Field(min_length=3, max_length=80)
    target_public_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_ATLAS_ACTIONS:
            raise ValueError(
                "Ação não suportada pelo contrato Atlas/Nexyra CRM."
            )
        return normalized


class AtlasActionExecuteRequest(AtlasActionRequest):
    confirmed: bool = False


class AtlasActionPreviewRead(BaseModel):
    contract_version: str
    action: str
    target_public_id: str | None
    allowed: bool
    confirmation_required: bool
    summary: str
    normalized_payload: dict[str, object]


class AtlasActionExecutionRead(BaseModel):
    contract_version: str
    action: str
    target_public_id: str | None
    executed: bool
    result: dict[str, object]
