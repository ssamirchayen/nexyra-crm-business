from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas.lead_recommendation import LeadRecommendationBoardRead
from app.services.lead_recommendation import LeadRecommendationService
from app.services.workspace import WorkspaceNotFoundError

router = APIRouter(tags=["lead-recommendations"])

DbSession = Annotated[Session, Depends(get_db)]
CanReadLeads = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("leads.read")),
]
OwnerFilter = Annotated[str | None, Query(max_length=64)]
UrgencyFilter = Annotated[
    str | None,
    Query(pattern="^(critical|high|medium|low)$"),
]
ActionFilter = Annotated[
    str | None,
    Query(
        pattern=(
            "^(assign_owner|reply_whatsapp|first_contact|follow_up|"
            "recover_opportunity|reengage|enroll_cadence|advance_opportunity|"
            "review_lead)$"
        )
    ),
]
LimitFilter = Annotated[int, Query(ge=1, le=500)]


@router.get(
    "/workspaces/{workspace_public_id}/lead-recommendations",
    response_model=LeadRecommendationBoardRead,
)
def get_lead_recommendations(
    workspace_public_id: str,
    db: DbSession,
    _authorization: CanReadLeads,
    owner_user_public_id: OwnerFilter = None,
    urgency: UrgencyFilter = None,
    action: ActionFilter = None,
    limit: LimitFilter = 150,
) -> LeadRecommendationBoardRead:
    try:
        payload = LeadRecommendationService(db).board(
            workspace_public_id,
            owner_user_public_id=owner_user_public_id,
            urgency=urgency,
            action=action,
            limit=limit,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LeadRecommendationBoardRead.model_validate(payload)
