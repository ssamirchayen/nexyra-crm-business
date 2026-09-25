from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import IntegrationSource, Lead, WhatsAppMessage, Workspace

ADMIN_PASSWORD = "Nexyra@Inbox123"
ADMIN_FINAL_PASSWORD = "Nexyra@Inbox456"


@pytest.fixture
def client_and_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, testing_session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _bootstrap_admin(client: TestClient) -> tuple[dict[str, object], dict[str, str]]:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Inbox Workspace",
            "slug": "inbox-workspace",
            "segment": "generic",
        },
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    member = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Inbox Admin",
            "email": "inbox-admin@nexyra.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert member.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inbox-admin@nexyra.demo",
            "password": ADMIN_PASSWORD,
        },
    )
    assert login.status_code == 200
    temp_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=temp_headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": ADMIN_FINAL_PASSWORD,
        },
    )
    assert changed.status_code == 200
    relogin = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inbox-admin@nexyra.demo",
            "password": ADMIN_FINAL_PASSWORD,
        },
    )
    assert relogin.status_code == 200
    return workspace, {
        "Authorization": f"Bearer {relogin.json()['access_token']}"
    }


def _seed_conversation(
    client: TestClient,
    testing_session: sessionmaker[Session],
    workspace: dict[str, object],
    headers: dict[str, str],
) -> tuple[str, str]:
    source_response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations",
        headers=headers,
        json={
            "provider": "whatsapp",
            "name": "WhatsApp Comercial",
            "source": "whatsapp",
            "channel": "inbound",
            "default_campaign": "Atendimento",
            "routing_config": {},
            "provider_config": {},
            "active": True,
        },
    )
    assert source_response.status_code == 201
    source_public_id = source_response.json()["public_id"]

    lead_response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=headers,
        json={
            "name": "Maria Inbox",
            "phone": "5592999991111",
            "interest": "Radiologia",
            "source": "whatsapp",
            "channel": "inbound",
            "status": "novo",
            "priority": "alta",
            "consent": True,
        },
    )
    assert lead_response.status_code == 201

    now = datetime.now(timezone.utc)
    with testing_session() as db:
        workspace_model = db.scalar(
            select(Workspace).where(Workspace.public_id == workspace["public_id"])
        )
        source = db.scalar(
            select(IntegrationSource).where(
                IntegrationSource.public_id == source_public_id
            )
        )
        lead = db.scalar(select(Lead).where(Lead.public_id == lead_response.json()["public_id"]))
        assert workspace_model is not None
        assert source is not None
        assert lead is not None

        db.add_all(
            [
                WhatsAppMessage(
                    workspace_id=workspace_model.id,
                    integration_source_id=source.id,
                    lead_id=lead.id,
                    provider_message_id="wamid.inbox.1",
                    direction="inbound",
                    message_type="text",
                    from_phone="5592999991111",
                    to_phone="5592888880000",
                    body="Olá, quero saber sobre o curso.",
                    status="received",
                    provider_timestamp=now - timedelta(minutes=2),
                    metadata_json={},
                ),
                WhatsAppMessage(
                    workspace_id=workspace_model.id,
                    integration_source_id=source.id,
                    lead_id=lead.id,
                    provider_message_id="wamid.inbox.2",
                    direction="outbound",
                    message_type="text",
                    from_phone="5592888880000",
                    to_phone="5592999991111",
                    body="Olá Maria! Posso ajudar.",
                    status="delivered",
                    provider_timestamp=now - timedelta(minutes=1),
                    metadata_json={},
                ),
            ]
        )
        db.commit()

    return source_public_id, "5592999991111"


def test_inbox_lists_whatsapp_conversation_with_unread_count(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source_public_id, phone = _seed_conversation(
        client,
        testing_session,
        workspace,
        headers,
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/inbox/conversations",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["integration_public_id"] == source_public_id
    assert payload[0]["contact_phone"] == phone
    assert payload[0]["lead_name"] == "Maria Inbox"
    assert payload[0]["last_message_body"] == "Olá Maria! Posso ajudar."
    assert payload[0]["unread_count"] == 1


def test_inbox_thread_can_be_marked_read_per_membership(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source_public_id, phone = _seed_conversation(
        client,
        testing_session,
        workspace,
        headers,
    )
    base = (
        f"/api/v1/workspaces/{workspace['public_id']}/inbox/conversations/"
        f"whatsapp/{source_public_id}/{phone}"
    )

    thread = client.get(base, headers=headers)
    assert thread.status_code == 200
    assert len(thread.json()["messages"]) == 2
    assert thread.json()["conversation"]["unread_count"] == 1

    marked = client.post(f"{base}/read", headers=headers)
    assert marked.status_code == 200
    assert marked.json()["marked"] == 1

    refreshed = client.get(base, headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["conversation"]["unread_count"] == 0
    inbound = next(
        item
        for item in refreshed.json()["messages"]
        if item["direction"] == "inbound"
    )
    assert inbound["read"] is True


def test_inbox_search_and_unread_filter(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source_public_id, phone = _seed_conversation(
        client,
        testing_session,
        workspace,
        headers,
    )

    search = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/inbox/conversations?q=Maria",
        headers=headers,
    )
    assert search.status_code == 200
    assert len(search.json()) == 1

    base = (
        f"/api/v1/workspaces/{workspace['public_id']}/inbox/conversations/"
        f"whatsapp/{source_public_id}/{phone}"
    )
    assert client.post(f"{base}/read", headers=headers).status_code == 200

    unread = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/inbox/conversations?unread_only=true",
        headers=headers,
    )
    assert unread.status_code == 200
    assert unread.json() == []
