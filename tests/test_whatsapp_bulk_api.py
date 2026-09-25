from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.integrations.whatsapp_cloud import WhatsAppGraphClient, WhatsAppTemplateInfo
from app.main import app
from app.models import WhatsAppMessage

ADMIN_PASSWORD = "Nexyra@Bulk123"
ADMIN_FINAL_PASSWORD = "Nexyra@Bulk456"


@pytest.fixture
def client_and_session() -> Generator[
    tuple[TestClient, sessionmaker[Session]], None, None
]:
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
        json={"name": "Bulk Workspace", "slug": "bulk-workspace", "segment": "generic"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    member = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Bulk Admin",
            "email": "bulk-admin@nexyra.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert member.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "bulk-admin@nexyra.demo", "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": ADMIN_FINAL_PASSWORD},
    )
    assert changed.status_code == 200
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "bulk-admin@nexyra.demo", "password": ADMIN_FINAL_PASSWORD},
    )
    assert relogin.status_code == 200
    return workspace, {"Authorization": f"Bearer {relogin.json()['access_token']}"}


def _integration(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
) -> dict[str, object]:
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations",
        headers=headers,
        json={
            "provider": "whatsapp",
            "name": "WhatsApp Lote",
            "source": "whatsapp",
            "channel": "outbound",
            "default_campaign": "Lote",
            "routing_config": {},
            "provider_config": {},
            "active": True,
        },
    )
    assert created.status_code == 201
    source = created.json()
    configured = client.put(
        (
            f"/api/v1/workspaces/{workspace_id}/integrations/"
            f"{source['public_id']}/whatsapp"
        ),
        headers=headers,
        json={
            "phone_number_id": "PHONE-BULK",
            "business_account_id": "WABA-BULK",
            "access_token": "EAATEST_BULK_ACCESS_TOKEN_1234567890",
        },
    )
    assert configured.status_code == 200
    return source


def _lead(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
    *,
    name: str,
    phone: str | None,
    interest: str = "Radiologia",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        headers=headers,
        json={
            "name": name,
            "phone": phone,
            "interest": interest,
            "source": "site",
            "channel": "web",
            "priority": "media",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _template() -> WhatsAppTemplateInfo:
    return WhatsAppTemplateInfo(
        name="retorno_lead",
        language="pt_BR",
        status="APPROVED",
        category="UTILITY",
        components=[
            {
                "type": "BODY",
                "text": "Olá {{1}}, recebemos seu interesse em {{2}}.",
            }
        ],
    )


def test_bulk_preview_resolves_variables_and_blocks_missing_phone(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _integration(client, workspace["public_id"], headers)
    first = _lead(
        client,
        workspace["public_id"],
        headers,
        name="Maria",
        phone="+55 (92) 98888-1111",
    )
    second = _lead(
        client,
        workspace["public_id"],
        headers,
        name="Sem Telefone",
        phone=None,
    )
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "list_message_templates",
        lambda self, business_account_id, *, limit=100: [_template()],
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/whatsapp/bulk/preview",
        headers=headers,
        json={
            "lead_public_ids": [first["public_id"], second["public_id"]],
            "integration_public_id": source["public_id"],
            "template_name": "retorno_lead",
            "language_code": "pt_BR",
            "parameter_templates": ["{{lead_name}}", "{{interest}}"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["eligible"] == 1
    assert payload["blocked"] == 1
    assert payload["recipients"][0]["parameters"] == ["Maria", "Radiologia"]
    assert payload["recipients"][0]["rendered_text"] == (
        "Olá Maria, recebemos seu interesse em Radiologia."
    )
    assert payload["recipients"][1]["eligible"] is False


def test_bulk_send_requires_preview_and_sends_only_eligible(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _integration(client, workspace["public_id"], headers)
    first = _lead(
        client,
        workspace["public_id"],
        headers,
        name="Ana",
        phone="5592999990001",
        interest="Enfermagem",
    )
    second = _lead(
        client,
        workspace["public_id"],
        headers,
        name="Bruno",
        phone="5592999990002",
        interest="Radiologia",
    )
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "list_message_templates",
        lambda self, business_account_id, *, limit=100: [_template()],
    )
    sent_to: list[str] = []

    def fake_send(
        self,
        *,
        phone_number_id: str,
        to: str,
        template_name: str,
        language_code: str,
        body_parameters: list[str],
    ) -> str:
        sent_to.append(to)
        return f"wamid.BULK-{len(sent_to)}"

    monkeypatch.setattr(WhatsAppGraphClient, "send_template", fake_send)
    request = {
        "lead_public_ids": [first["public_id"], second["public_id"]],
        "integration_public_id": source["public_id"],
        "template_name": "retorno_lead",
        "language_code": "pt_BR",
        "parameter_templates": ["{{lead_name}}", "{{interest}}"],
    }
    preview = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/whatsapp/bulk/preview",
        headers=headers,
        json=request,
    )
    assert preview.status_code == 200, preview.text
    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/whatsapp/bulk/send",
        headers=headers,
        json={**request, "confirmation_token": preview.json()["confirmation_token"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sent"] == 2
    assert payload["failed"] == 0
    assert sent_to == ["5592999990001", "5592999990002"]

    with testing_session() as db:
        stored = list(db.scalars(select(WhatsAppMessage)).all())
        assert len(stored) == 2
        assert all(message.message_type == "template" for message in stored)


def test_bulk_confirmation_rejects_changed_selection(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _integration(client, workspace["public_id"], headers)
    first = _lead(
        client,
        workspace["public_id"],
        headers,
        name="Carlos",
        phone="5592999990003",
    )
    second = _lead(
        client,
        workspace["public_id"],
        headers,
        name="Diana",
        phone="5592999990004",
    )
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "list_message_templates",
        lambda self, business_account_id, *, limit=100: [_template()],
    )
    request = {
        "lead_public_ids": [first["public_id"]],
        "integration_public_id": source["public_id"],
        "template_name": "retorno_lead",
        "language_code": "pt_BR",
        "parameter_templates": ["{{lead_name}}", "{{interest}}"],
    }
    preview = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/whatsapp/bulk/preview",
        headers=headers,
        json=request,
    )
    assert preview.status_code == 200
    changed = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/whatsapp/bulk/send",
        headers=headers,
        json={
            **request,
            "lead_public_ids": [first["public_id"], second["public_id"]],
            "confirmation_token": preview.json()["confirmation_token"],
        },
    )
    assert changed.status_code == 409
