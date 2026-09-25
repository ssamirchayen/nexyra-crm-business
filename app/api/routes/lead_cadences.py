from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import (
    LeadCadenceCreate,
    LeadCadenceEnrollmentRead,
    LeadCadenceEnrollRequest,
    LeadCadencePreviewItem,
    LeadCadencePreviewRead,
    LeadCadenceProcessRead,
    LeadCadenceRead,
    LeadCadenceStepRead,
    LeadCadenceUpdate,
)
from app.services.lead_cadence import (
    CadenceView,
    EnrollmentView,
    LeadCadenceEnrollmentError,
    LeadCadenceNotFoundError,
    LeadCadenceService,
)
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["lead-cadences"])
DbSession = Annotated[Session, Depends(get_db)]
CanRead = Annotated[WorkspaceAuthorization, Depends(require_workspace_permission("leads.read"))]
CanManage = Annotated[WorkspaceAuthorization, Depends(require_workspace_permission("settings.update"))]
CanOperate = Annotated[WorkspaceAuthorization, Depends(require_workspace_permission("activities.create"))]
StartAtQuery = Annotated[datetime | None, Query()]
ProcessLimitQuery = Annotated[int, Query(ge=1, le=500)]


def _error(exc: ValueError) -> None:
    if isinstance(exc, (WorkspaceNotFoundError, LeadCadenceNotFoundError)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, LeadCadenceEnrollmentError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


def _cadence_read(view: CadenceView) -> LeadCadenceRead:
    return LeadCadenceRead(
        public_id=view.cadence.public_id,
        name=view.cadence.name,
        description=view.cadence.description,
        active=view.cadence.active,
        stop_on_reply=view.cadence.stop_on_reply,
        steps=[
            LeadCadenceStepRead(
                position=step.position,
                delay_minutes=step.delay_minutes,
                action_type=step.action_type,
                title=step.title,
                message_template=step.message_template,
            )
            for step in view.steps
        ],
        active_enrollments=view.active_enrollments,
        created_at=view.cadence.created_at,
        updated_at=view.cadence.updated_at,
    )


def _enrollment_read(view: EnrollmentView) -> LeadCadenceEnrollmentRead:
    item = view.enrollment
    return LeadCadenceEnrollmentRead(
        public_id=item.public_id,
        lead_public_id=view.lead.public_id,
        lead_name=view.lead.name,
        cadence_public_id=view.cadence.public_id,
        cadence_name=view.cadence.name,
        status=item.status,
        current_step=item.current_step,
        total_steps=view.total_steps,
        next_run_at=item.next_run_at,
        started_at=item.started_at,
        completed_at=item.completed_at,
        cancelled_at=item.cancelled_at,
    )


@router.get("/workspaces/{workspace_public_id}/lead-cadences", response_model=list[LeadCadenceRead])
def list_cadences(workspace_public_id: str, db: DbSession, _authorization: CanRead) -> list[LeadCadenceRead]:
    return [_cadence_read(item) for item in LeadCadenceService(db).list(workspace_public_id)]


@router.post("/workspaces/{workspace_public_id}/lead-cadences", response_model=LeadCadenceRead, status_code=status.HTTP_201_CREATED)
def create_cadence(workspace_public_id: str, payload: LeadCadenceCreate, db: DbSession, _authorization: CanManage) -> LeadCadenceRead:
    try:
        return _cadence_read(LeadCadenceService(db).create(workspace_public_id, payload))
    except ValueError as exc:
        _error(exc)
        raise


@router.put("/workspaces/{workspace_public_id}/lead-cadences/{cadence_public_id}", response_model=LeadCadenceRead)
def update_cadence(workspace_public_id: str, cadence_public_id: str, payload: LeadCadenceUpdate, db: DbSession, _authorization: CanManage) -> LeadCadenceRead:
    try:
        return _cadence_read(LeadCadenceService(db).update(workspace_public_id, cadence_public_id, payload))
    except ValueError as exc:
        _error(exc)
        raise


@router.get("/workspaces/{workspace_public_id}/lead-cadences/{cadence_public_id}/preview", response_model=LeadCadencePreviewRead)
def preview_cadence(workspace_public_id: str, cadence_public_id: str, db: DbSession, _authorization: CanRead, start_at: StartAtQuery = None) -> LeadCadencePreviewRead:
    try:
        items = LeadCadenceService(db).preview(workspace_public_id, cadence_public_id, start_at=start_at)
    except ValueError as exc:
        _error(exc)
        raise
    return LeadCadencePreviewRead(items=[LeadCadencePreviewItem(position=step.position, scheduled_at=when, action_type=step.action_type, title=step.title) for step, when in items])


@router.get("/workspaces/{workspace_public_id}/lead-cadence-enrollments", response_model=list[LeadCadenceEnrollmentRead])
def list_enrollments(workspace_public_id: str, db: DbSession, _authorization: CanRead) -> list[LeadCadenceEnrollmentRead]:
    return [_enrollment_read(item) for item in LeadCadenceService(db).list_enrollments(workspace_public_id)]


@router.post("/workspaces/{workspace_public_id}/lead-cadence-enrollments", response_model=LeadCadenceEnrollmentRead, status_code=status.HTTP_201_CREATED)
def enroll(workspace_public_id: str, payload: LeadCadenceEnrollRequest, db: DbSession, _authorization: CanOperate) -> LeadCadenceEnrollmentRead:
    try:
        return _enrollment_read(LeadCadenceService(db).enroll(workspace_public_id, lead_public_id=payload.lead_public_id, cadence_public_id=payload.cadence_public_id))
    except ValueError as exc:
        _error(exc)
        raise


@router.post("/workspaces/{workspace_public_id}/lead-cadence-enrollments/{enrollment_public_id}/cancel", response_model=LeadCadenceEnrollmentRead)
def cancel(workspace_public_id: str, enrollment_public_id: str, db: DbSession, _authorization: CanOperate) -> LeadCadenceEnrollmentRead:
    try:
        return _enrollment_read(LeadCadenceService(db).cancel(workspace_public_id, enrollment_public_id))
    except ValueError as exc:
        _error(exc)
        raise


@router.post("/workspaces/{workspace_public_id}/lead-cadences/process-due", response_model=LeadCadenceProcessRead)
def process_due(workspace_public_id: str, db: DbSession, _authorization: CanOperate, limit: ProcessLimitQuery = 100) -> LeadCadenceProcessRead:
    try:
        result = LeadCadenceService(db).process_due(workspace_public_id, limit=limit)
    except ValueError as exc:
        _error(exc)
        raise
    return LeadCadenceProcessRead(**result.__dict__)
