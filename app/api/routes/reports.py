from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas.reports import ReportAnalyticsRead
from app.services.reports import ReportOwnerNotFoundError, ReportsService
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["reports"])

DbSession = Annotated[Session, Depends(get_db)]
PeriodDays = Annotated[int, Query(ge=7, le=365)]
FilterCode = Annotated[str | None, Query(max_length=160)]
CanReadAnalytics = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("analytics.read")),
]


@router.get(
    "/workspaces/{workspace_public_id}/reports/analytics",
    response_model=ReportAnalyticsRead,
)
def reports_analytics(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadAnalytics,
    period_days: PeriodDays = 30,
    source: FilterCode = None,
    owner_user_public_id: FilterCode = None,
) -> ReportAnalyticsRead:
    try:
        payload = ReportsService(db).analytics(
            workspace_public_id,
            period_days=period_days,
            source=source,
            owner_user_public_id=owner_user_public_id,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportOwnerNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ReportAnalyticsRead(**payload)
