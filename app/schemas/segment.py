from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_FIELD_PATTERN = re.compile(r"^[a-z0-9_]+$")
_STAGE_PATTERN = re.compile(r"^[a-z0-9_]+$")


class SegmentDefinitionRead(BaseModel):
    code: str
    label: str
    interest_label: str
    pipeline: list[str]
    custom_fields: list[str]


class WorkspaceSegmentConfigUpdate(BaseModel):
    segment_code: str = Field(min_length=2, max_length=50)
    interest_label: str | None = Field(default=None, min_length=2, max_length=80)
    pipeline: list[str] | None = Field(default=None, min_length=2, max_length=30)
    custom_fields: list[str] | None = Field(default=None, max_length=50)

    @field_validator("segment_code")
    @classmethod
    def normalize_segment_code(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    @field_validator("interest_label")
    @classmethod
    def normalize_interest_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())

    @field_validator("pipeline")
    @classmethod
    def validate_pipeline(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        normalized = [item.strip().lower().replace(" ", "_") for item in value]

        if len(set(normalized)) != len(normalized):
            raise ValueError("As etapas do pipeline não podem se repetir.")

        if any(not _STAGE_PATTERN.fullmatch(item) for item in normalized):
            raise ValueError(
                "As etapas devem usar apenas letras minúsculas, números e underscore."
            )

        return normalized

    @field_validator("custom_fields")
    @classmethod
    def validate_custom_fields(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        normalized = [item.strip().lower().replace(" ", "_") for item in value]

        if len(set(normalized)) != len(normalized):
            raise ValueError("Os campos personalizados não podem se repetir.")

        if any(not _FIELD_PATTERN.fullmatch(item) for item in normalized):
            raise ValueError(
                "Os campos devem usar apenas letras minúsculas, números e underscore."
            )

        return normalized


class WorkspaceSegmentConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    segment_code: str
    interest_label: str
    pipeline: list[str]
    custom_fields: list[str]
