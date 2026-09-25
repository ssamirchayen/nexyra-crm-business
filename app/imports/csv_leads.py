from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.integrations.catalog import get_provider_definition
from app.models import IntegrationSource, LeadImportJob, Workspace
from app.repositories import (
    IntegrationSourceRepository,
    LeadImportJobRepository,
    WorkspaceRepository,
    WorkspaceSegmentConfigRepository,
)
from app.schemas import LeadCreate
from app.schemas.lead_import import (
    CsvImportExecuteRead,
    CsvImportOptionsRead,
    CsvImportPreviewRead,
    CsvImportPreviewRow,
    CsvImportSourceOptionRead,
    CsvLeadImportRequest,
    LeadImportJobRead,
)
from app.segments.catalog import get_segment_definition
from app.services.audit import AuditService
from app.services.lead import LeadDuplicateError, LeadService

CSV_IMPORT_MAX_ROWS = 5_000
CSV_IMPORT_MAX_CHARS = 3_000_000
CSV_IMPORT_ERROR_SAMPLE_LIMIT = 30
CSV_IMPORT_PREVIEW_SAMPLE_LIMIT = 12

_SUPPORTED_FIELDS = (
    "name",
    "phone",
    "email",
    "external_id",
    "interest",
    "campaign",
    "message",
    "status",
    "priority",
    "consent",
)

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": (
        "name",
        "nome",
        "nome completo",
        "nome_completo",
        "full name",
        "full_name",
        "cliente",
        "lead",
    ),
    "phone": (
        "phone",
        "telefone",
        "celular",
        "mobile",
        "whatsapp",
        "fone",
    ),
    "email": ("email", "e-mail", "mail", "correio"),
    "external_id": (
        "external id",
        "external_id",
        "lead id",
        "lead_id",
        "id",
        "codigo",
        "código",
    ),
    "interest": (
        "interest",
        "interesse",
        "curso",
        "produto",
        "servico",
        "serviço",
    ),
    "campaign": ("campaign", "campanha", "utm campaign", "utm_campaign"),
    "message": (
        "message",
        "mensagem",
        "observacao",
        "observação",
        "notes",
        "nota",
    ),
    "status": ("status", "etapa", "stage", "fase"),
    "priority": ("priority", "prioridade"),
    "consent": ("consent", "consentimento", "lgpd", "lgpd consent"),
}


class CsvLeadImportError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCsv:
    delimiter: str
    headers: list[str]
    rows: list[dict[str, str]]


@dataclass(frozen=True)
class ResolvedImportSource:
    integration: IntegrationSource | None
    source: str
    channel: str
    campaign: str | None


def _normalize_header(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_value = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(ascii_value.replace("-", " ").replace("_", " ").split())


def _normalize_bool(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "sim", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "nao", "não", "no", "n", "off"}:
        return False
    raise CsvLeadImportError(f"Consentimento inválido: {value!r}.")


def _display_delimiter(delimiter: str) -> str:
    return "\\t" if delimiter == "\t" else delimiter


def _actual_delimiter(value: str) -> str:
    return "\t" if value == "\\t" else value


class CsvLeadImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.sources = IntegrationSourceRepository(db)
        self.segment_configs = WorkspaceSegmentConfigRepository(db)
        self.jobs = LeadImportJobRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str) -> Workspace:
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise CsvLeadImportError(f"Empresa não encontrada: {public_id}")
        return workspace

    def _pipeline(self, workspace: Workspace) -> list[str]:
        config = self.segment_configs.get_by_workspace_id(workspace.id)
        if config is not None:
            return list(config.pipeline)
        definition = get_segment_definition(workspace.segment)
        return list(definition.pipeline) if definition is not None else ["novo"]

    def _resolve_source(
        self,
        workspace: Workspace,
        request: CsvLeadImportRequest,
    ) -> ResolvedImportSource:
        if not request.integration_public_id:
            return ResolvedImportSource(
                integration=None,
                source=request.source,
                channel=request.channel,
                campaign=request.campaign,
            )

        item = self.sources.get_by_public_id(
            workspace_id=workspace.id,
            public_id=request.integration_public_id,
        )
        if item is None:
            raise CsvLeadImportError("Fonte CSV não encontrada nesta empresa.")
        if not item.active:
            raise CsvLeadImportError("A fonte CSV selecionada está desativada.")
        provider = get_provider_definition(item.provider)
        if provider is None or provider.code != "csv":
            raise CsvLeadImportError(
                "A fonte selecionada não é do tipo Importação CSV."
            )
        return ResolvedImportSource(
            integration=item,
            source=item.source,
            channel=item.channel,
            campaign=request.campaign or item.default_campaign,
        )

    def _parse(self, request: CsvLeadImportRequest) -> ParsedCsv:
        text = request.csv_text
        if len(text) > CSV_IMPORT_MAX_CHARS:
            raise CsvLeadImportError(
                f"O CSV excede o limite de {CSV_IMPORT_MAX_CHARS:,} caracteres."
            )

        normalized_text = text.lstrip("\ufeff")
        if not normalized_text.strip():
            raise CsvLeadImportError("O arquivo CSV está vazio.")

        if request.delimiter == "auto":
            try:
                dialect = csv.Sniffer().sniff(
                    normalized_text[:8192], delimiters=",;\t|"
                )
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ";" if ";" in normalized_text.splitlines()[0] else ","
        else:
            delimiter = _actual_delimiter(request.delimiter)

        reader = csv.DictReader(io.StringIO(normalized_text), delimiter=delimiter)
        if not reader.fieldnames:
            raise CsvLeadImportError("Não foi possível identificar o cabeçalho do CSV.")

        headers = [
            str(header or "").strip().lstrip("\ufeff")
            for header in reader.fieldnames
        ]
        if any(not header for header in headers):
            raise CsvLeadImportError("O CSV possui coluna sem nome no cabeçalho.")
        reader.fieldnames = headers
        normalized_headers = [_normalize_header(header) for header in headers]
        if len(set(normalized_headers)) != len(normalized_headers):
            raise CsvLeadImportError("O CSV possui colunas duplicadas no cabeçalho.")

        rows: list[dict[str, str]] = []
        for raw_row in reader:
            if len(rows) >= CSV_IMPORT_MAX_ROWS:
                raise CsvLeadImportError(
                    "O arquivo excede o limite de "
                    f"{CSV_IMPORT_MAX_ROWS} linhas por importação."
                )
            row: dict[str, str] = {}
            for header in headers:
                value = raw_row.get(header)
                row[header] = "" if value is None else str(value).strip()
            if any(value for value in row.values()):
                rows.append(row)

        if not rows:
            raise CsvLeadImportError("O CSV não possui linhas de dados.")

        return ParsedCsv(
            delimiter=_display_delimiter(delimiter),
            headers=headers,
            rows=rows,
        )

    def _auto_mapping(self, headers: list[str]) -> dict[str, str]:
        normalized_to_original = {
            _normalize_header(header): header for header in headers
        }
        mapping: dict[str, str] = {}
        for destination, aliases in _FIELD_ALIASES.items():
            for alias in aliases:
                matched = normalized_to_original.get(_normalize_header(alias))
                if matched is not None:
                    mapping[destination] = matched
                    break
        return mapping

    def _mapping(
        self,
        request: CsvLeadImportRequest,
        headers: list[str],
    ) -> dict[str, str]:
        mapping = self._auto_mapping(headers)
        header_set = set(headers)
        for destination, header in request.field_mapping.items():
            if destination not in _SUPPORTED_FIELDS:
                continue
            if header not in header_set:
                raise CsvLeadImportError(
                    f"A coluna mapeada '{header}' não existe no CSV."
                )
            mapping[destination] = header
        if "name" not in mapping:
            raise CsvLeadImportError(
                "Não foi possível identificar a coluna de nome. "
                "Mapeie uma coluna para 'name'."
            )
        return mapping

    def _build_payload(
        self,
        *,
        row: dict[str, str],
        mapping: dict[str, str],
        source: ResolvedImportSource,
        request: CsvLeadImportRequest,
        pipeline: list[str],
    ) -> LeadCreate:
        values: dict[str, Any] = {}
        for destination, header in mapping.items():
            raw = row.get(header, "").strip()
            if raw:
                values[destination] = raw

        if not values.get("name"):
            raise CsvLeadImportError("Nome do lead não informado.")

        if "consent" in values:
            values["consent"] = _normalize_bool(
                str(values["consent"]), request.consent_default
            )
        else:
            values["consent"] = request.consent_default

        if not values.get("status") and request.default_status:
            values["status"] = request.default_status
        if not values.get("priority"):
            values["priority"] = request.default_priority

        status_value = values.get("status")
        if status_value:
            normalized_status = str(status_value).strip().lower().replace(" ", "_")
            if normalized_status not in pipeline:
                raise CsvLeadImportError(
                    f"Status '{normalized_status}' não pertence ao pipeline da empresa."
                )
            values["status"] = normalized_status

        values["source"] = source.source
        values["channel"] = source.channel
        if not values.get("campaign") and source.campaign:
            values["campaign"] = source.campaign

        try:
            return LeadCreate.model_validate(values)
        except ValidationError as exc:
            messages = [
                str(item.get("msg", "Valor inválido."))
                for item in exc.errors(include_url=False, include_input=False)
            ]
            raise CsvLeadImportError("; ".join(messages)) from exc

    def options(self, workspace_public_id: str) -> CsvImportOptionsRead:
        workspace = self._workspace(workspace_public_id)
        sources = [
            CsvImportSourceOptionRead(
                public_id=item.public_id,
                name=item.name,
                source=item.source,
                channel=item.channel,
                default_campaign=item.default_campaign,
            )
            for item in self.sources.list_for_workspace(workspace.id)
            if item.active and item.provider == "csv"
        ]
        return CsvImportOptionsRead(
            sources=sources,
            max_rows=CSV_IMPORT_MAX_ROWS,
            max_file_chars=CSV_IMPORT_MAX_CHARS,
            supported_fields=list(_SUPPORTED_FIELDS),
        )

    def preview(
        self,
        workspace_public_id: str,
        request: CsvLeadImportRequest,
    ) -> CsvImportPreviewRead:
        workspace = self._workspace(workspace_public_id)
        parsed = self._parse(request)
        mapping = self._mapping(request, parsed.headers)
        source = self._resolve_source(workspace, request)
        pipeline = self._pipeline(workspace)

        valid_rows = 0
        invalid_rows = 0
        samples: list[CsvImportPreviewRow] = []
        for index, row in enumerate(parsed.rows, start=2):
            errors: list[str] = []
            values: dict[str, object] = {}
            try:
                payload = self._build_payload(
                    row=row,
                    mapping=mapping,
                    source=source,
                    request=request,
                    pipeline=pipeline,
                )
                values = payload.model_dump()
                valid_rows += 1
            except CsvLeadImportError as exc:
                invalid_rows += 1
                errors.append(str(exc))
                values = {
                    destination: row.get(header, "")
                    for destination, header in mapping.items()
                    if row.get(header, "")
                }

            if len(samples) < CSV_IMPORT_PREVIEW_SAMPLE_LIMIT:
                samples.append(
                    CsvImportPreviewRow(
                        row_number=index,
                        valid=not errors,
                        values=values,
                        errors=errors,
                    )
                )

        warnings: list[str] = []
        if invalid_rows:
            warnings.append(
                f"{invalid_rows} linha(s) possuem erro e não serão importadas."
            )
        if request.duplicate_mode == "update":
            warnings.append(
                "Leads duplicados por telefone, e-mail ou ID externo serão atualizados."
            )
        else:
            warnings.append("Leads duplicados serão ignorados sem alteração.")

        return CsvImportPreviewRead(
            filename=request.filename,
            delimiter=parsed.delimiter,
            headers=parsed.headers,
            field_mapping=mapping,
            total_rows=len(parsed.rows),
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            sample_rows=samples,
            warnings=warnings,
        )

    def execute(
        self,
        workspace_public_id: str,
        request: CsvLeadImportRequest,
    ) -> CsvImportExecuteRead:
        workspace = self._workspace(workspace_public_id)
        parsed = self._parse(request)
        mapping = self._mapping(request, parsed.headers)
        source = self._resolve_source(workspace, request)
        pipeline = self._pipeline(workspace)

        job = self.jobs.create(
            workspace_id=workspace.id,
            integration_source_id=source.integration.id if source.integration else None,
            filename=request.filename,
            delimiter=parsed.delimiter,
            duplicate_mode=request.duplicate_mode,
            source=source.source,
            channel=source.channel,
            campaign=source.campaign,
            field_mapping=dict(mapping),
            total_rows=len(parsed.rows),
        )
        self.db.commit()
        self.db.refresh(job)

        created = 0
        updated = 0
        skipped = 0
        failed = 0
        error_samples: list[dict[str, object]] = []
        lead_service = LeadService(self.db)

        for row_number, row in enumerate(parsed.rows, start=2):
            try:
                payload = self._build_payload(
                    row=row,
                    mapping=mapping,
                    source=source,
                    request=request,
                    pipeline=pipeline,
                )
                if request.duplicate_mode == "update":
                    action, _ = lead_service.intake(workspace_public_id, payload)
                    if action == "created":
                        created += 1
                    else:
                        updated += 1
                else:
                    try:
                        lead_service.create(workspace_public_id, payload)
                        created += 1
                    except LeadDuplicateError:
                        skipped += 1
            except ValueError as exc:
                failed += 1
                if len(error_samples) < CSV_IMPORT_ERROR_SAMPLE_LIMIT:
                    error_samples.append(
                        {
                            "row_number": row_number,
                            "message": str(exc),
                            "name": row.get(mapping.get("name", ""), ""),
                        }
                    )

        job = self.db.get(LeadImportJob, job.id)
        if job is None:
            raise CsvLeadImportError(
                "Não foi possível finalizar o registro da importação."
            )
        job.created_count = created
        job.updated_count = updated
        job.skipped_count = skipped
        job.failed_count = failed
        job.error_samples = error_samples
        job.status = "completed_with_errors" if failed else "completed"
        job.completed_at = datetime.now(timezone.utc)
        self.jobs.save(job)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="lead_import",
            entity_public_id=job.public_id,
            action="lead_import.completed",
            after_data={
                "filename": job.filename,
                "source": job.source,
                "channel": job.channel,
                "total_rows": job.total_rows,
                "created_count": created,
                "updated_count": updated,
                "skipped_count": skipped,
                "failed_count": failed,
                "status": job.status,
            },
        )
        self.db.commit()
        self.db.refresh(job)

        return CsvImportExecuteRead(
            job=LeadImportJobRead.model_validate(job),
            created=created,
            duplicate_updated=updated,
            duplicate_skipped=skipped,
            failed=failed,
            error_samples=error_samples,
        )

    def list_jobs(self, workspace_public_id: str) -> list[LeadImportJobRead]:
        workspace = self._workspace(workspace_public_id)
        return [
            LeadImportJobRead.model_validate(job)
            for job in self.jobs.list_recent(workspace.id)
        ]
