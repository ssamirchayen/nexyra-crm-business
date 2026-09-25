from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CsvDelimiter = Literal["auto", ",", ";", "\\t", "|"]
DuplicateMode = Literal["update", "skip"]

_CODE_PATTERN = re.compile(r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")


class CsvLeadImportRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    csv_text: str = Field(min_length=1, max_length=3_000_000)
    delimiter: CsvDelimiter = "auto"
    integration_public_id: str | None = Field(default=None, max_length=32)
    duplicate_mode: DuplicateMode = "update"
    source: str = Field(default="csv", min_length=2, max_length=80)
    channel: str = Field(default="import", min_length=2, max_length=80)
    campaign: str | None = Field(default=None, max_length=160)
    default_status: str | None = Field(default=None, max_length=80)
    default_priority: str = Field(default="media", max_length=20)
    consent_default: bool = True
    field_mapping: dict[str, str] = Field(default_factory=dict)

    @field_validator("filename")
    @classmethod
    def normalize_filename(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Informe o nome do arquivo CSV.")
        return normalized

    @field_validator("source", "channel")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_")
        if not _CODE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Use apenas letras minúsculas, números, hífen ou underline."
            )
        return normalized

    @field_validator("campaign", "default_status")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("field_mapping")
    @classmethod
    def normalize_mapping(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for destination, header in value.items():
            dest = destination.strip()
            source_header = header.strip()
            if dest and source_header:
                normalized[dest] = source_header
        return normalized


class CsvImportPreviewRow(BaseModel):
    row_number: int
    valid: bool
    values: dict[str, object]
    errors: list[str]


class CsvImportPreviewRead(BaseModel):
    filename: str
    delimiter: str
    headers: list[str]
    field_mapping: dict[str, str]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    sample_rows: list[CsvImportPreviewRow]
    warnings: list[str]


class CsvImportSourceOptionRead(BaseModel):
    public_id: str
    name: str
    source: str
    channel: str
    default_campaign: str | None


class CsvImportOptionsRead(BaseModel):
    sources: list[CsvImportSourceOptionRead]
    max_rows: int
    max_file_chars: int
    supported_fields: list[str]


class LeadImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    filename: str
    delimiter: str
    duplicate_mode: str
    source: str
    channel: str
    campaign: str | None
    status: str
    total_rows: int
    created_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    field_mapping: dict[str, object]
    error_samples: list[dict[str, object]]
    created_at: datetime
    completed_at: datetime | None


class CsvImportExecuteRead(BaseModel):
    job: LeadImportJobRead
    created: int
    duplicate_updated: int
    duplicate_skipped: int
    failed: int
    error_samples: list[dict[str, object]]
