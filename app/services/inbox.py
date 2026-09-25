from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    IntegrationSource,
    Lead,
    User,
    WhatsAppMessage,
    WorkspaceMembership,
)
from app.repositories import WorkspaceRepository


class InboxWorkspaceNotFoundError(ValueError):
    pass


class InboxConversationNotFoundError(ValueError):
    pass


class InboxService:
    """Operational inbox built on top of provider message records.

    Sprint 4 / Etapa 7 starts with WhatsApp, but keeps the API shaped as an
    inbox so additional channels can be introduced without changing the UI
    contract.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)

    @staticmethod
    def _event_time(message: WhatsAppMessage) -> datetime:
        value = message.provider_timestamp or message.created_at
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _contact_phone(message: WhatsAppMessage) -> str | None:
        value = (
            message.from_phone
            if message.direction == "inbound"
            else message.to_phone
        )
        if not value:
            return None
        digits = "".join(char for char in value if char.isdigit())
        return digits or None

    @staticmethod
    def conversation_key(integration_public_id: str, contact_phone: str) -> str:
        return f"whatsapp:{integration_public_id}:{quote(contact_phone, safe='')}"

    @staticmethod
    def _read_by(message: WhatsAppMessage) -> set[int]:
        metadata = message.metadata_json or {}
        raw = metadata.get("inbox_read_by_membership_ids", [])
        if not isinstance(raw, list):
            return set()
        values: set[int] = set()
        for item in raw:
            try:
                values.add(int(item))
            except (TypeError, ValueError):
                continue
        return values

    def _workspace_id(self, workspace_public_id: str) -> int:
        workspace = self.workspaces.get_by_public_id(workspace_public_id)
        if workspace is None:
            raise InboxWorkspaceNotFoundError("Empresa não encontrada.")
        return workspace.id

    def _context_maps(
        self,
        *,
        workspace_id: int,
        messages: list[WhatsAppMessage],
    ) -> tuple[
        dict[int, IntegrationSource],
        dict[int, Lead],
        dict[int, tuple[str, str]],
    ]:
        source_ids = {item.integration_source_id for item in messages}
        lead_ids = {item.lead_id for item in messages if item.lead_id is not None}

        sources: dict[int, IntegrationSource] = {}
        if source_ids:
            rows = self.db.scalars(
                select(IntegrationSource).where(
                    IntegrationSource.workspace_id == workspace_id,
                    IntegrationSource.id.in_(source_ids),
                )
            ).all()
            sources = {item.id: item for item in rows}

        leads: dict[int, Lead] = {}
        if lead_ids:
            rows = self.db.scalars(
                select(Lead).where(
                    Lead.workspace_id == workspace_id,
                    Lead.id.in_(lead_ids),
                )
            ).all()
            leads = {item.id: item for item in rows}

        owner_membership_ids = {
            lead.owner_membership_id
            for lead in leads.values()
            if lead.owner_membership_id is not None
        }
        owners: dict[int, tuple[str, str]] = {}
        if owner_membership_ids:
            statement = (
                select(WorkspaceMembership.id, User.public_id, User.name)
                .join(User, User.id == WorkspaceMembership.user_id)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.id.in_(owner_membership_ids),
                )
            )
            owners = {
                membership_id: (public_id, name)
                for membership_id, public_id, name in self.db.execute(statement)
            }

        return sources, leads, owners

    def _conversation_payload(
        self,
        *,
        source: IntegrationSource,
        contact_phone: str,
        messages: list[WhatsAppMessage],
        leads: dict[int, Lead],
        owners: dict[int, tuple[str, str]],
        membership_id: int | None,
    ) -> dict[str, object]:
        ordered = sorted(messages, key=self._event_time, reverse=True)
        latest = ordered[0]
        lead = next(
            (leads[item.lead_id] for item in ordered if item.lead_id in leads),
            None,
        )
        owner_public_id: str | None = None
        owner_name: str | None = None
        if lead is not None and lead.owner_membership_id in owners:
            owner_public_id, owner_name = owners[lead.owner_membership_id]

        unread_count = 0
        if membership_id is not None:
            unread_count = sum(
                1
                for item in ordered
                if item.direction == "inbound"
                and membership_id not in self._read_by(item)
            )

        return {
            "conversation_key": self.conversation_key(
                source.public_id,
                contact_phone,
            ),
            "channel": "whatsapp",
            "integration_public_id": source.public_id,
            "integration_name": source.name,
            "contact_phone": contact_phone,
            "lead_public_id": lead.public_id if lead is not None else None,
            "lead_name": lead.name if lead is not None else None,
            "lead_status": lead.status if lead is not None else None,
            "lead_priority": lead.priority if lead is not None else None,
            "owner_user_public_id": owner_public_id,
            "owner_name": owner_name,
            "last_message_public_id": latest.public_id,
            "last_message_direction": latest.direction,
            "last_message_type": latest.message_type,
            "last_message_body": latest.body,
            "last_message_status": latest.status,
            "last_message_at": self._event_time(latest),
            "unread_count": unread_count,
        }

    def list_conversations(
        self,
        workspace_public_id: str,
        *,
        membership_id: int | None,
        query: str | None = None,
        unread_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        workspace_id = self._workspace_id(workspace_public_id)
        messages = list(
            self.db.scalars(
                select(WhatsAppMessage)
                .where(WhatsAppMessage.workspace_id == workspace_id)
                .order_by(WhatsAppMessage.id.desc())
                .limit(5000)
            ).all()
        )
        if not messages:
            return []

        sources, leads, owners = self._context_maps(
            workspace_id=workspace_id,
            messages=messages,
        )
        grouped: dict[tuple[int, str], list[WhatsAppMessage]] = defaultdict(list)
        for message in messages:
            source = sources.get(message.integration_source_id)
            if source is None or source.provider != "whatsapp":
                continue
            contact_phone = self._contact_phone(message)
            if contact_phone:
                grouped[(source.id, contact_phone)].append(message)

        normalized_query = (query or "").strip().lower()
        payloads: list[dict[str, object]] = []
        for (source_id, contact_phone), group in grouped.items():
            source = sources[source_id]
            payload = self._conversation_payload(
                source=source,
                contact_phone=contact_phone,
                messages=group,
                leads=leads,
                owners=owners,
                membership_id=membership_id,
            )
            if unread_only and int(payload["unread_count"]) == 0:
                continue
            if normalized_query:
                haystack = " ".join(
                    str(payload.get(key) or "")
                    for key in (
                        "contact_phone",
                        "lead_name",
                        "last_message_body",
                        "integration_name",
                    )
                ).lower()
                if normalized_query not in haystack:
                    continue
            payloads.append(payload)

        payloads.sort(
            key=lambda item: item["last_message_at"],
            reverse=True,
        )
        return payloads[:limit]

    def _thread_messages(
        self,
        *,
        workspace_id: int,
        integration_public_id: str,
        contact_phone: str,
        limit: int,
    ) -> tuple[IntegrationSource, list[WhatsAppMessage]]:
        source = self.db.scalar(
            select(IntegrationSource).where(
                IntegrationSource.workspace_id == workspace_id,
                IntegrationSource.public_id == integration_public_id,
                IntegrationSource.provider == "whatsapp",
            )
        )
        if source is None:
            raise InboxConversationNotFoundError("Conversa não encontrada.")

        all_messages = list(
            self.db.scalars(
                select(WhatsAppMessage)
                .where(
                    WhatsAppMessage.workspace_id == workspace_id,
                    WhatsAppMessage.integration_source_id == source.id,
                )
                .order_by(WhatsAppMessage.id.desc())
                .limit(max(limit * 5, 500))
            ).all()
        )
        selected = [
            message
            for message in all_messages
            if self._contact_phone(message) == contact_phone
        ][:limit]
        if not selected:
            raise InboxConversationNotFoundError("Conversa não encontrada.")
        return source, selected

    def get_thread(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        contact_phone: str,
        *,
        membership_id: int | None,
        limit: int = 200,
    ) -> dict[str, object]:
        workspace_id = self._workspace_id(workspace_public_id)
        normalized_phone = "".join(char for char in contact_phone if char.isdigit())
        source, messages = self._thread_messages(
            workspace_id=workspace_id,
            integration_public_id=integration_public_id,
            contact_phone=normalized_phone,
            limit=limit,
        )
        _, leads, owners = self._context_maps(
            workspace_id=workspace_id,
            messages=messages,
        )
        conversation = self._conversation_payload(
            source=source,
            contact_phone=normalized_phone,
            messages=messages,
            leads=leads,
            owners=owners,
            membership_id=membership_id,
        )
        ordered = sorted(messages, key=self._event_time)
        return {
            "conversation": conversation,
            "messages": [
                {
                    "public_id": item.public_id,
                    "provider_message_id": item.provider_message_id,
                    "direction": item.direction,
                    "message_type": item.message_type,
                    "from_phone": item.from_phone,
                    "to_phone": item.to_phone,
                    "body": item.body,
                    "status": item.status,
                    "error_code": item.error_code,
                    "error_message": item.error_message,
                    "provider_timestamp": item.provider_timestamp,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    "read": (
                        item.direction != "inbound"
                        or membership_id is None
                        or membership_id in self._read_by(item)
                    ),
                }
                for item in ordered
            ],
        }

    def mark_read(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        contact_phone: str,
        *,
        membership_id: int | None,
    ) -> dict[str, object]:
        workspace_id = self._workspace_id(workspace_public_id)
        normalized_phone = "".join(char for char in contact_phone if char.isdigit())
        _, messages = self._thread_messages(
            workspace_id=workspace_id,
            integration_public_id=integration_public_id,
            contact_phone=normalized_phone,
            limit=500,
        )
        marked = 0
        if membership_id is not None:
            now = datetime.now(timezone.utc).isoformat()
            for message in messages:
                if message.direction != "inbound":
                    continue
                read_by = self._read_by(message)
                if membership_id in read_by:
                    continue
                read_by.add(membership_id)
                metadata = dict(message.metadata_json or {})
                metadata["inbox_read_by_membership_ids"] = sorted(read_by)
                metadata["inbox_last_read_at"] = now
                message.metadata_json = metadata
                self.db.add(message)
                marked += 1
            if marked:
                self.db.commit()

        return {
            "ok": True,
            "marked": marked,
            "conversation_key": self.conversation_key(
                integration_public_id,
                normalized_phone,
            ),
        }
