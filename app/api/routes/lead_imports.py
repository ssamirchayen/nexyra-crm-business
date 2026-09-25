from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.imports import CsvLeadImportError, CsvLeadImportService
from app.schemas.lead_import import (
    CsvImportExecuteRead,
    CsvImportOptionsRead,
    CsvImportPreviewRead,
    CsvLeadImportRequest,
    LeadImportJobRead,
)

router = APIRouter(tags=["lead-imports"])
DbSession = Annotated[Session, Depends(get_db)]
CanCreateLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.create")),
]
CanReadLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.read")),
]


def _translate_error(exc: ValueError) -> None:
    detail = str(exc)
    if "Empresa não encontrada" in detail:
        raise HTTPException(status_code=404, detail=detail) from exc
    raise HTTPException(status_code=422, detail=detail) from exc


@router.get(
    "/workspaces/{workspace_public_id}/lead-imports/options",
    response_model=CsvImportOptionsRead,
)
def csv_import_options(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanCreateLeads,
) -> CsvImportOptionsRead:
    try:
        return CsvLeadImportService(db).options(workspace_public_id)
    except CsvLeadImportError as exc:
        _translate_error(exc)
        raise


@router.post(
    "/workspaces/{workspace_public_id}/lead-imports/preview",
    response_model=CsvImportPreviewRead,
)
def preview_csv_import(
    workspace_public_id: str,
    payload: CsvLeadImportRequest,
    db: DbSession,
    _authorization: CanCreateLeads,
) -> CsvImportPreviewRead:
    try:
        return CsvLeadImportService(db).preview(workspace_public_id, payload)
    except CsvLeadImportError as exc:
        _translate_error(exc)
        raise


@router.post(
    "/workspaces/{workspace_public_id}/lead-imports/execute",
    response_model=CsvImportExecuteRead,
)
def execute_csv_import(
    workspace_public_id: str,
    payload: CsvLeadImportRequest,
    db: DbSession,
    _authorization: CanCreateLeads,
) -> CsvImportExecuteRead:
    try:
        return CsvLeadImportService(db).execute(workspace_public_id, payload)
    except CsvLeadImportError as exc:
        _translate_error(exc)
        raise


@router.get(
    "/workspaces/{workspace_public_id}/lead-imports",
    response_model=list[LeadImportJobRead],
)
def list_csv_imports(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
) -> list[LeadImportJobRead]:
    try:
        return CsvLeadImportService(db).list_jobs(workspace_public_id)
    except CsvLeadImportError as exc:
        _translate_error(exc)
        raise
