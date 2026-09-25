from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AppSecurity,
    WorkspaceAuthorization,
    ensure_can_assign_user,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import (
    ActivityCardRead,
    ActivityCreate,
    ActivityPageRead,
    ActivityRead,
    ActivityUpdate,
    PendingActivityRead,
)
from app.schemas.activity import VALID_ACTIVITY_TYPES
from app.services import (
    ActivityCardView,
    ActivityNotFoundError,
    ActivityOwnerError,
    ActivityService,
    ActivityStateError,
    ActivityTargetError,
    ActivityView,
    WorkspaceNotFoundError,
)

router = APIRouter(tags=["activities"])

DbSession = Annotated[Session, Depends(get_db)]
SearchQuery = Annotated[str | None, Query(max_length=160)]
FilterCode = Annotated[str | None, Query(max_length=100)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
CanReadActivities = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("activities.read")),
]
CanCreateActivities = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("activities.create")),
]
CanUpdateActivities = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("activities.update")),
]


def _serialize(view: ActivityView) -> ActivityRead:
    item = view.activity

    return ActivityRead(
        public_id=item.public_id,
        activity_type=item.activity_type,
        title=item.title,
        description=item.description,
        status=item.status,
        due_at=item.due_at,
        completed_at=item.completed_at,
        cancelled_at=item.cancelled_at,
        lead_public_id=view.lead_public_id,
        opportunity_public_id=view.opportunity_public_id,
        owner_user_public_id=view.owner_user_public_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _serialize_card(view: ActivityCardView) -> ActivityCardRead:
    item = view.activity

    return ActivityCardRead(
        public_id=item.public_id,
        activity_type=item.activity_type,
        title=item.title,
        description=item.description,
        status=item.status,
        due_at=item.due_at,
        completed_at=item.completed_at,
        cancelled_at=item.cancelled_at,
        lead_public_id=view.lead_public_id,
        opportunity_public_id=view.opportunity_public_id,
        owner_user_public_id=view.owner_user_public_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        lead_name=view.lead_name,
        opportunity_title=view.opportunity_title,
        owner_name=view.owner_name,
        overdue=view.overdue,
    )


def _translate_error(exc: ValueError) -> None:
    if isinstance(
        exc,
        (
            WorkspaceNotFoundError,
            ActivityNotFoundError,
            ActivityTargetError,
        ),
    ):
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if isinstance(
        exc,
        (
            ActivityOwnerError,
            ActivityStateError,
        ),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    raise exc


@router.get(
    "/activity-types",
    response_model=list[str],
)
def list_activity_types(_security: AppSecurity) -> list[str]:
    return sorted(VALID_ACTIVITY_TYPES)


@router.post(
    "/workspaces/{workspace_public_id}/activities",
    response_model=ActivityRead,
    status_code=201,
)
def create_activity(
    workspace_public_id: str,
    payload: ActivityCreate,
    db: DbSession,
    authorization: CanCreateActivities,
) -> ActivityRead:
    if payload.owner_user_public_id is not None:
        ensure_can_assign_user(authorization, payload.owner_user_public_id)

    try:
        view = ActivityService(db).create(
            workspace_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.get(
    "/workspaces/{workspace_public_id}/activities",
    response_model=list[ActivityRead],
)
def list_activities(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadActivities,
) -> list[ActivityRead]:
    try:
        views = ActivityService(db).list_all(workspace_public_id)
    except ValueError as exc:
        _translate_error(exc)
        raise

    return [_serialize(view) for view in views]


@router.get(
    "/workspaces/{workspace_public_id}/activities/search",
    response_model=ActivityPageRead,
)
def search_activities(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadActivities,
    q: SearchQuery = None,
    activity_type: FilterCode = None,
    activity_status: Annotated[
        str | None,
        Query(alias="status", max_length=30),
    ] = None,
    owner_user_public_id: FilterCode = None,
    unassigned: bool = False,
    overdue: bool | None = None,
    due_from: datetime | None = None,
    due_to: datetime | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
) -> ActivityPageRead:
    try:
        result = ActivityService(db).search(
            workspace_public_id,
            query=q,
            activity_type=activity_type,
            status=activity_status,
            owner_user_public_id=owner_user_public_id,
            only_unassigned=unassigned,
            overdue=overdue,
            due_from=due_from,
            due_to=due_to,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    total_pages = ceil(result.total / result.page_size) if result.total else 0
    return ActivityPageRead(
        items=[_serialize_card(view) for view in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=total_pages,
    )


@router.get(
    "/workspaces/{workspace_public_id}/activities/{activity_public_id}",
    response_model=ActivityRead,
)
def get_activity(
    workspace_public_id: str,
    activity_public_id: str,
    db: DbSession,
    _authorization: CanReadActivities,
) -> ActivityRead:
    try:
        view = ActivityService(db).get(
            workspace_public_id,
            activity_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.patch(
    "/workspaces/{workspace_public_id}/activities/{activity_public_id}",
    response_model=ActivityRead,
)
def update_activity(
    workspace_public_id: str,
    activity_public_id: str,
    payload: ActivityUpdate,
    db: DbSession,
    authorization: CanUpdateActivities,
) -> ActivityRead:
    if "owner_user_public_id" in payload.model_fields_set:
        ensure_can_assign_user(authorization, payload.owner_user_public_id)

    try:
        view = ActivityService(db).update(
            workspace_public_id,
            activity_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.post(
    "/workspaces/{workspace_public_id}/activities/"
    "{activity_public_id}/complete",
    response_model=ActivityRead,
)
def complete_activity(
    workspace_public_id: str,
    activity_public_id: str,
    db: DbSession,
    _authorization: CanUpdateActivities,
) -> ActivityRead:
    try:
        view = ActivityService(db).complete(
            workspace_public_id,
            activity_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.post(
    "/workspaces/{workspace_public_id}/activities/"
    "{activity_public_id}/cancel",
    response_model=ActivityRead,
)
def cancel_activity(
    workspace_public_id: str,
    activity_public_id: str,
    db: DbSession,
    _authorization: CanUpdateActivities,
) -> ActivityRead:
    try:
        view = ActivityService(db).cancel(
            workspace_public_id,
            activity_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.get(
    "/workspaces/{workspace_public_id}/leads/"
    "{lead_public_id}/activities",
    response_model=list[ActivityRead],
)
def lead_activities(
    workspace_public_id: str,
    lead_public_id: str,
    db: DbSession,
    _authorization: CanReadActivities,
) -> list[ActivityRead]:
    try:
        views = ActivityService(db).list_for_lead(
            workspace_public_id,
            lead_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return [_serialize(view) for view in views]


@router.get(
    "/workspaces/{workspace_public_id}/opportunities/"
    "{opportunity_public_id}/activities",
    response_model=list[ActivityRead],
)
def opportunity_activities(
    workspace_public_id: str,
    opportunity_public_id: str,
    db: DbSession,
    _authorization: CanReadActivities,
) -> list[ActivityRead]:
    try:
        views = ActivityService(db).list_for_opportunity(
            workspace_public_id,
            opportunity_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return [_serialize(view) for view in views]


@router.get(
    "/workspaces/{workspace_public_id}/follow-ups/pending",
    response_model=list[PendingActivityRead],
)
def pending_follow_ups(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadActivities,
) -> list[PendingActivityRead]:
    try:
        views = ActivityService(db).pending(
            workspace_public_id
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    service = ActivityService(db)

    return [
        PendingActivityRead(
            **_serialize(view).model_dump(),
            overdue=service.is_overdue(view.activity),
        )
        for view in views
    ]
