from __future__ import annotations

from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    ensure_can_assign_user,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas import (
    OpportunityCardRead,
    OpportunityCreate,
    OpportunityLost,
    OpportunityMetricsRead,
    OpportunityMove,
    OpportunityPageRead,
    OpportunityRead,
    OpportunityStageHistoryRead,
    OpportunityUpdate,
    OpportunityWon,
    PipelineBoardRead,
    PipelineStageRead,
)
from app.services import (
    OpportunityCardView,
    OpportunityHistoryView,
    OpportunityLeadError,
    OpportunityNotFoundError,
    OpportunityOwnerError,
    OpportunityService,
    OpportunityStageError,
    OpportunityStateError,
    OpportunityView,
    WorkspaceNotFoundError,
)

router = APIRouter(tags=["opportunities"])

DbSession = Annotated[Session, Depends(get_db)]
SearchQuery = Annotated[str | None, Query(max_length=160)]
FilterCode = Annotated[str | None, Query(max_length=160)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
CanReadPipeline = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("pipeline.read")),
]
CanUpdatePipeline = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("pipeline.update")),
]
CanReadAnalytics = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("analytics.read")),
]


def _serialize(view: OpportunityView) -> OpportunityRead:
    item = view.opportunity

    return OpportunityRead(
        public_id=item.public_id,
        lead_public_id=view.lead_public_id,
        owner_user_public_id=view.owner_user_public_id,
        title=item.title,
        value_amount=item.value_amount,
        currency=item.currency,
        stage=item.stage,
        status=item.status,
        expected_close_date=item.expected_close_date,
        loss_reason=item.loss_reason,
        won_at=item.won_at,
        lost_at=item.lost_at,
    )


def _serialize_card(view: OpportunityCardView) -> OpportunityCardRead:
    item = view.opportunity
    lead = view.lead

    return OpportunityCardRead(
        public_id=item.public_id,
        lead_public_id=lead.public_id,
        lead_name=lead.name,
        lead_phone=lead.phone,
        lead_email=lead.email,
        lead_interest=lead.interest,
        owner_user_public_id=view.owner_user_public_id,
        owner_name=view.owner_name,
        title=item.title,
        value_amount=item.value_amount,
        currency=item.currency,
        stage=item.stage,
        status=item.status,
        expected_close_date=item.expected_close_date,
        loss_reason=item.loss_reason,
        won_at=item.won_at,
        lost_at=item.lost_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _serialize_history(
    view: OpportunityHistoryView,
) -> OpportunityStageHistoryRead:
    item = view.history

    return OpportunityStageHistoryRead(
        from_stage=item.from_stage,
        to_stage=item.to_stage,
        changed_by_user_public_id=(
            view.changed_by_user_public_id
        ),
        note=item.note,
        created_at=item.created_at,
    )


def _translate_error(exc: ValueError) -> None:
    if isinstance(
        exc,
        (
            WorkspaceNotFoundError,
            OpportunityNotFoundError,
            OpportunityLeadError,
        ),
    ):
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if isinstance(
        exc,
        (
            OpportunityOwnerError,
            OpportunityStageError,
            OpportunityStateError,
        ),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    raise exc


@router.post(
    "/workspaces/{workspace_public_id}/opportunities",
    response_model=OpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_opportunity(
    workspace_public_id: str,
    payload: OpportunityCreate,
    db: DbSession,
    authorization: CanUpdatePipeline,
) -> OpportunityRead:
    if payload.owner_user_public_id is not None:
        ensure_can_assign_user(authorization, payload.owner_user_public_id)

    try:
        view = OpportunityService(db).create(
            workspace_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.get(
    "/workspaces/{workspace_public_id}/opportunities",
    response_model=list[OpportunityRead],
)
def list_opportunities(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadPipeline,
) -> list[OpportunityRead]:
    try:
        views = OpportunityService(db).list_all(
            workspace_public_id
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return [_serialize(view) for view in views]


@router.get(
    "/workspaces/{workspace_public_id}/opportunities/search",
    response_model=OpportunityPageRead,
)
def search_opportunities(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadPipeline,
    q: SearchQuery = None,
    stage: FilterCode = None,
    opportunity_status: FilterCode = None,
    owner_user_public_id: FilterCode = None,
    unassigned: bool = False,
    page: PageNumber = 1,
    page_size: PageSize = 20,
) -> OpportunityPageRead:
    try:
        result = OpportunityService(db).search(
            workspace_public_id,
            query=q,
            stage=stage,
            status=opportunity_status,
            owner_user_public_id=owner_user_public_id,
            only_unassigned=unassigned,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    total_pages = ceil(result.total / result.page_size) if result.total else 0

    return OpportunityPageRead(
        items=[_serialize_card(view) for view in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=total_pages,
    )


@router.get(
    "/workspaces/{workspace_public_id}/pipeline/board",
    response_model=PipelineBoardRead,
)
def pipeline_board(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadPipeline,
    q: SearchQuery = None,
    owner_user_public_id: FilterCode = None,
    unassigned: bool = False,
) -> PipelineBoardRead:
    try:
        board = OpportunityService(db).pipeline_board(
            workspace_public_id,
            query=q,
            owner_user_public_id=owner_user_public_id,
            only_unassigned=unassigned,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return PipelineBoardRead(
        workspace_public_id=board.workspace_public_id,
        pipeline=board.pipeline,
        open_opportunities=board.open_opportunities,
        total_pipeline_value=board.total_pipeline_value,
        stages=[
            PipelineStageRead(
                code=stage.code,
                total_count=stage.total_count,
                total_value=stage.total_value,
                opportunities=[
                    _serialize_card(view)
                    for view in stage.opportunities
                ],
            )
            for stage in board.stages
        ],
    )


@router.get(
    "/workspaces/{workspace_public_id}/opportunities/{opportunity_public_id}",
    response_model=OpportunityRead,
)
def get_opportunity(
    workspace_public_id: str,
    opportunity_public_id: str,
    db: DbSession,
    _authorization: CanReadPipeline,
) -> OpportunityRead:
    try:
        view = OpportunityService(db).get(
            workspace_public_id,
            opportunity_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.patch(
    "/workspaces/{workspace_public_id}/opportunities/{opportunity_public_id}",
    response_model=OpportunityRead,
)
def update_opportunity(
    workspace_public_id: str,
    opportunity_public_id: str,
    payload: OpportunityUpdate,
    db: DbSession,
    authorization: CanUpdatePipeline,
) -> OpportunityRead:
    if "owner_user_public_id" in payload.model_fields_set:
        ensure_can_assign_user(authorization, payload.owner_user_public_id)

    try:
        view = OpportunityService(db).update(
            workspace_public_id,
            opportunity_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.post(
    "/workspaces/{workspace_public_id}/opportunities/"
    "{opportunity_public_id}/move",
    response_model=OpportunityRead,
)
def move_opportunity(
    workspace_public_id: str,
    opportunity_public_id: str,
    payload: OpportunityMove,
    db: DbSession,
    authorization: CanUpdatePipeline,
) -> OpportunityRead:
    if authorization.user_public_id is not None:
        payload = payload.model_copy(
            update={"changed_by_user_public_id": authorization.user_public_id}
        )

    try:
        view = OpportunityService(db).move(
            workspace_public_id,
            opportunity_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.post(
    "/workspaces/{workspace_public_id}/opportunities/"
    "{opportunity_public_id}/won",
    response_model=OpportunityRead,
)
def mark_opportunity_won(
    workspace_public_id: str,
    opportunity_public_id: str,
    payload: OpportunityWon,
    db: DbSession,
    authorization: CanUpdatePipeline,
) -> OpportunityRead:
    if authorization.user_public_id is not None:
        payload = payload.model_copy(
            update={"changed_by_user_public_id": authorization.user_public_id}
        )

    try:
        view = OpportunityService(db).mark_won(
            workspace_public_id,
            opportunity_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.post(
    "/workspaces/{workspace_public_id}/opportunities/"
    "{opportunity_public_id}/lost",
    response_model=OpportunityRead,
)
def mark_opportunity_lost(
    workspace_public_id: str,
    opportunity_public_id: str,
    payload: OpportunityLost,
    db: DbSession,
    authorization: CanUpdatePipeline,
) -> OpportunityRead:
    if authorization.user_public_id is not None:
        payload = payload.model_copy(
            update={"changed_by_user_public_id": authorization.user_public_id}
        )

    try:
        view = OpportunityService(db).mark_lost(
            workspace_public_id,
            opportunity_public_id,
            payload,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return _serialize(view)


@router.get(
    "/workspaces/{workspace_public_id}/opportunities/"
    "{opportunity_public_id}/history",
    response_model=list[OpportunityStageHistoryRead],
)
def opportunity_history(
    workspace_public_id: str,
    opportunity_public_id: str,
    db: DbSession,
    _authorization: CanReadPipeline,
) -> list[OpportunityStageHistoryRead]:
    try:
        views = OpportunityService(db).history(
            workspace_public_id,
            opportunity_public_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return [
        _serialize_history(view)
        for view in views
    ]


@router.get(
    "/workspaces/{workspace_public_id}/analytics/conversion",
    response_model=OpportunityMetricsRead,
)
def opportunity_metrics(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadAnalytics,
) -> OpportunityMetricsRead:
    try:
        metrics = OpportunityService(db).metrics(
            workspace_public_id
        )
    except ValueError as exc:
        _translate_error(exc)
        raise

    return OpportunityMetricsRead(**metrics)
