from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AppSecurity,
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from app.services import (
    WorkspaceNotFoundError,
    WorkspaceService,
    WorkspaceSlugConflictError,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadWorkspace = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("workspace.read")),
]
CanUpdateWorkspace = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("workspace.update")),
]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    db: DbSession,
    security: AppSecurity,
) -> WorkspaceRead:
    try:
        workspace = WorkspaceService(db).create(
            payload,
            creator_user_id=(
                security.auth.user.id if security.auth is not None else None
            ),
        )
    except WorkspaceSlugConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WorkspaceRead.model_validate(workspace)


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(
    db: DbSession,
    security: AppSecurity,
) -> list[WorkspaceRead]:
    if security.bootstrap:
        workspaces = WorkspaceService(db).list_all()
    else:
        assert security.auth is not None
        workspaces = [access.workspace for access in security.auth.workspaces]

    return [WorkspaceRead.model_validate(item) for item in workspaces]


@router.get("/{public_id}", response_model=WorkspaceRead)
def get_workspace(
    public_id: str,
    db: DbSession,
    _authorization: CanReadWorkspace,
) -> WorkspaceRead:
    try:
        workspace = WorkspaceService(db).get(public_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WorkspaceRead.model_validate(workspace)


@router.patch("/{public_id}", response_model=WorkspaceRead)
def update_workspace(
    public_id: str,
    payload: WorkspaceUpdate,
    db: DbSession,
    _authorization: CanUpdateWorkspace,
) -> WorkspaceRead:
    try:
        workspace = WorkspaceService(db).update(public_id, payload)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceSlugConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WorkspaceRead.model_validate(workspace)


@router.post("/{public_id}/deactivate", response_model=WorkspaceRead)
def deactivate_workspace(
    public_id: str,
    db: DbSession,
    _authorization: CanUpdateWorkspace,
) -> WorkspaceRead:
    try:
        workspace = WorkspaceService(db).deactivate(public_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WorkspaceRead.model_validate(workspace)
