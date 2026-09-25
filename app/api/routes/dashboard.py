from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import DashboardSummaryRead
from app.schemas.dashboard import DashboardOperationalRead
from app.services import DashboardService, WorkspaceNotFoundError
from app.services.operational_dashboard import OperationalDashboardService
from app.services.reports import ReportOwnerNotFoundError

router = APIRouter(tags=["dashboard"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadWorkspace = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("workspace.read")),
]

CanReadAnalytics = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("analytics.read")),
]
PeriodDays = Annotated[int, Query(ge=7, le=365)]
OwnerFilter = Annotated[str | None, Query(max_length=64)]


@router.get(
    "/workspaces/{workspace_public_id}/dashboard/summary",
    response_model=DashboardSummaryRead,
)
def dashboard_summary(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadWorkspace,
) -> DashboardSummaryRead:
    try:
        summary = DashboardService(db).summary(workspace_public_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DashboardSummaryRead(**summary)


@router.get(
    "/workspaces/{workspace_public_id}/dashboard/operations",
    response_model=DashboardOperationalRead,
)
def dashboard_operations(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadAnalytics,
    period_days: PeriodDays = 30,
    owner_user_public_id: OwnerFilter = None,
) -> DashboardOperationalRead:
    try:
        payload = OperationalDashboardService(db).overview(
            workspace_public_id,
            period_days=period_days,
            owner_user_public_id=owner_user_public_id,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportOwnerNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DashboardOperationalRead.model_validate(payload)
