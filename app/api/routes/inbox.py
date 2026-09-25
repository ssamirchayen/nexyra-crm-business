from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    WorkspaceAuthorization,
    require_workspace_permission,
)
from app.db import get_db
from app.schemas.inbox import (
    InboxConversationRead,
    InboxMarkReadRead,
    InboxThreadRead,
)
from app.services.inbox import (
    InboxConversationNotFoundError,
    InboxService,
    InboxWorkspaceNotFoundError,
)

router = APIRouter(tags=["inbox"])
DbSession = Annotated[Session, Depends(get_db)]
CanReadInbox = Annotated[
    WorkspaceAuthorization,
    Depends(require_workspace_permission("activities.read")),
]


def _translate_error(exc: ValueError) -> None:
    if isinstance(exc, (InboxWorkspaceNotFoundError, InboxConversationNotFoundError)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise exc


@router.get(
    "/workspaces/{workspace_public_id}/inbox/conversations",
    response_model=list[InboxConversationRead],
)
def list_inbox_conversations(
    workspace_public_id: str,
    db: DbSession,
    authorization: CanReadInbox,
    q: Annotated[str | None, Query(max_length=160)] = None,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[InboxConversationRead]:
    try:
        items = InboxService(db).list_conversations(
            workspace_public_id,
            membership_id=authorization.membership_id,
            query=q,
            unread_only=unread_only,
            limit=limit,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return [InboxConversationRead(**item) for item in items]


@router.get(
    "/workspaces/{workspace_public_id}/inbox/conversations/whatsapp/"
    "{integration_public_id}/{contact_phone}",
    response_model=InboxThreadRead,
)
def get_inbox_thread(
    workspace_public_id: str,
    integration_public_id: str,
    contact_phone: str,
    db: DbSession,
    authorization: CanReadInbox,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> InboxThreadRead:
    try:
        result = InboxService(db).get_thread(
            workspace_public_id,
            integration_public_id,
            contact_phone,
            membership_id=authorization.membership_id,
            limit=limit,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return InboxThreadRead(**result)


@router.post(
    "/workspaces/{workspace_public_id}/inbox/conversations/whatsapp/"
    "{integration_public_id}/{contact_phone}/read",
    response_model=InboxMarkReadRead,
)
def mark_inbox_thread_read(
    workspace_public_id: str,
    integration_public_id: str,
    contact_phone: str,
    db: DbSession,
    authorization: CanReadInbox,
) -> InboxMarkReadRead:
    try:
        result = InboxService(db).mark_read(
            workspace_public_id,
            integration_public_id,
            contact_phone,
            membership_id=authorization.membership_id,
        )
    except ValueError as exc:
        _translate_error(exc)
        raise
    return InboxMarkReadRead(**result)
