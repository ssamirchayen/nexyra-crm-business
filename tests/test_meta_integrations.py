from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import Base, get_db
from app.integrations.meta_lead_ads import MetaGraphClient, MetaLeadData
from app.main import app
from app.models import IntegrationSecret, IntegrationSource, Lead

ADMIN_PASSWORD = "Nexyra@Meta123"
ADMIN_FINAL_PASSWORD = "Nexyra@Meta456"


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
        json={"name": "Meta Workspace", "slug": "meta-workspace", "segment": "generic"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    member = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Meta Admin",
            "email": "meta-admin@nexyra.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert member.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "meta-admin@nexyra.demo", "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    temp_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=temp_headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": ADMIN_FINAL_PASSWORD},
    )
    assert changed.status_code == 200
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "meta-admin@nexyra.demo", "password": ADMIN_FINAL_PASSWORD},
    )
    assert relogin.status_code == 200
    return workspace, {"Authorization": f"Bearer {relogin.json()['access_token']}"}


def _meta_source(client: TestClient, workspace_id: str, headers: dict[str, str], name: str = "Meta Ads") -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations",
        headers=headers,
        json={
            "provider": "meta",
            "name": name,
            "source": "instagram",
            "channel": "lead_ads",
            "default_campaign": "Meta Setembro",
            "routing_config": {},
            "provider_config": {},
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def _configure(client: TestClient, workspace_id: str, source_id: str, headers: dict[str, str], page_id: str = "123456789") -> dict[str, object]:
    response = client.put(
        f"/api/v1/workspaces/{workspace_id}/integrations/{source_id}/meta",
        headers=headers,
        json={
            "page_id": page_id,
            "page_access_token": "EAATEST_LONG_LIVED_PAGE_TOKEN_1234567890",
            "form_ids": ["FORM-1"],
            "interest_field": "produto",
            "default_interest": "Meta Lead Ads",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_meta_configuration_encrypts_page_token(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _meta_source(client, workspace["public_id"], headers)
    status = _configure(client, workspace["public_id"], source["public_id"], headers)

    assert status["configured"] is True
    assert status["page_id"] == "123456789"
    assert status["form_ids"] == ["FORM-1"]
    assert status["webhook_endpoint"] == "/meta/webhook"

    with testing_session() as db:
        stored = db.scalar(select(IntegrationSecret))
        assert stored is not None
        assert "EAATEST_LONG_LIVED_PAGE_TOKEN_1234567890" not in stored.encrypted_payload
        integration = db.scalar(
            select(IntegrationSource).where(IntegrationSource.public_id == source["public_id"])
        )
        assert integration is not None
        assert "page_access_token" not in integration.provider_config


def test_meta_page_id_cannot_be_bound_twice(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    first = _meta_source(client, workspace["public_id"], headers, "Meta A")
    second = _meta_source(client, workspace["public_id"], headers, "Meta B")
    _configure(client, workspace["public_id"], first["public_id"], headers, "PAGE-1")

    response = client.put(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/{second['public_id']}/meta",
        headers=headers,
        json={
            "page_id": "PAGE-1",
            "page_access_token": "EAATEST_OTHER_LONG_LIVED_PAGE_TOKEN_1234567890",
            "form_ids": [],
        },
    )
    assert response.status_code == 409


def test_meta_connection_test_uses_graph_client(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _meta_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    monkeypatch.setattr(
        MetaGraphClient,
        "test_page",
        lambda self, page_id: (page_id, "Página Nexyra"),
    )
    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/{source['public_id']}/meta/test",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["page_name"] == "Página Nexyra"



def test_meta_page_subscription_marks_source_as_subscribed(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _meta_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    settings = get_settings()
    monkeypatch.setattr(settings, "meta_app_secret", "meta-app-secret-test")
    monkeypatch.setattr(settings, "meta_webhook_verify_token", "verify-test")
    calls: list[str] = []
    monkeypatch.setattr(
        MetaGraphClient,
        "subscribe_page",
        lambda self, page_id: calls.append(page_id),
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/{source['public_id']}/meta/subscribe",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["subscribed"] is True
    assert calls == ["123456789"]

    status = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/{source['public_id']}/meta",
        headers=headers,
    )
    assert status.status_code == 200
    assert status.json()["subscribed"] is True

def test_meta_webhook_verification_challenge(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_webhook_verify_token", "verify-nexyra")

    response = client.get(
        "/api/v1/meta/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-nexyra",
            "hub.challenge": "CHALLENGE-123",
        },
    )
    assert response.status_code == 200
    assert response.text == "CHALLENGE-123"


def test_meta_webhook_creates_lead_and_validates_signature(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _meta_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    settings = get_settings()
    monkeypatch.setattr(settings, "meta_app_secret", "meta-app-secret-test")
    monkeypatch.setattr(settings, "meta_webhook_verify_token", "verify-test")
    monkeypatch.setattr(
        MetaGraphClient,
        "fetch_lead",
        lambda self, leadgen_id: MetaLeadData(
            leadgen_id=leadgen_id,
            form_id="FORM-1",
            campaign_name="Campanha Graph",
            fields={
                "full_name": "Lead Meta Teste",
                "email": "meta@example.com",
                "phone_number": "+5592999999999",
                "produto": "Atlas Pro",
            },
        ),
    )

    payload = {
        "object": "page",
        "entry": [
            {
                "id": "123456789",
                "time": 1,
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {
                            "page_id": "123456789",
                            "form_id": "FORM-1",
                            "leadgen_id": "LEADGEN-ABC",
                            "created_time": 1,
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(
        b"meta-app-secret-test", raw, hashlib.sha256
    ).hexdigest()

    response = client.post(
        "/api/v1/meta/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["created"] == 1

    with testing_session() as db:
        lead = db.scalar(select(Lead).where(Lead.external_id == "meta:LEADGEN-ABC"))
        assert lead is not None
        assert lead.name == "Lead Meta Teste"
        assert lead.source == "instagram"
        assert lead.channel == "lead_ads"
        assert lead.campaign == "Campanha Graph"
        assert lead.interest == "Atlas Pro"

    repeated = client.post(
        "/api/v1/meta/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["updated"] == 1


def test_meta_webhook_rejects_invalid_signature(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_app_secret", "meta-app-secret-test")

    response = client.post(
        "/api/v1/meta/webhook",
        json={"object": "page", "entry": []},
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert response.status_code == 401
