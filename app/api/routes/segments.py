from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AppSecurity,
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import (
    SegmentDefinitionRead,
    WorkspaceSegmentConfigRead,
    WorkspaceSegmentConfigUpdate,
)
from app.services import (
    SegmentNotFoundError,
    WorkspaceNotFoundError,
    WorkspaceSegmentService,
)

router = APIRouter(tags=["segments"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadWorkspace = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("workspace.read")),
]
CanUpdateSettings = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("settings.update")),
]


@router.get(
    "/segments",
    response_model=list[SegmentDefinitionRead],
)
def list_segments(
    db: DbSession,
    _security: AppSecurity,
) -> list[SegmentDefinitionRead]:
    service = WorkspaceSegmentService(db)

    return [
        SegmentDefinitionRead(
            code=item.code,
            label=item.label,
            interest_label=item.interest_label,
            pipeline=list(item.pipeline),
            custom_fields=list(item.custom_fields),
        )
        for item in service.list_catalog()
    ]


@router.get(
    "/segments/{code}",
    response_model=SegmentDefinitionRead,
)
def get_segment(
    code: str,
    db: DbSession,
    _security: AppSecurity,
) -> SegmentDefinitionRead:
    try:
        item = WorkspaceSegmentService(db).get_catalog_item(code)
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SegmentDefinitionRead(
        code=item.code,
        label=item.label,
        interest_label=item.interest_label,
        pipeline=list(item.pipeline),
        custom_fields=list(item.custom_fields),
    )


@router.get(
    "/workspaces/{public_id}/segment-config",
    response_model=WorkspaceSegmentConfigRead,
)
def get_workspace_segment_config(
    public_id: str,
    db: DbSession,
    _authorization: CanReadWorkspace,
) -> WorkspaceSegmentConfigRead:
    try:
        config = WorkspaceSegmentService(db).get_workspace_config(public_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return WorkspaceSegmentConfigRead.model_validate(config)


@router.put(
    "/workspaces/{public_id}/segment-config",
    response_model=WorkspaceSegmentConfigRead,
)
def update_workspace_segment_config(
    public_id: str,
    payload: WorkspaceSegmentConfigUpdate,
    db: DbSession,
    _authorization: CanUpdateSettings,
) -> WorkspaceSegmentConfigRead:
    try:
        config = WorkspaceSegmentService(db).update_workspace_config(
            public_id,
            payload,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return WorkspaceSegmentConfigRead.model_validate(config)
