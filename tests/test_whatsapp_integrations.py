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
from app.integrations.whatsapp_cloud import (
    WhatsAppGraphClient,
    WhatsAppPhoneInfo,
    WhatsAppTemplateInfo,
)
from app.main import app
from app.models import (
    Activity,
    IntegrationSecret,
    IntegrationSource,
    Lead,
    WhatsAppMessage,
)

ADMIN_PASSWORD = "Nexyra@Whats123"
ADMIN_FINAL_PASSWORD = "Nexyra@Whats456"


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
            "name": "WhatsApp Workspace",
            "slug": "whatsapp-workspace",
            "segment": "generic",
        },
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    member = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "WhatsApp Admin",
            "email": "whatsapp-admin@nexyra.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert member.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "whatsapp-admin@nexyra.demo",
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
            "email": "whatsapp-admin@nexyra.demo",
            "password": ADMIN_FINAL_PASSWORD,
        },
    )
    assert relogin.status_code == 200
    return workspace, {
        "Authorization": f"Bearer {relogin.json()['access_token']}"
    }


def _whatsapp_source(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
    name: str = "WhatsApp Comercial",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations",
        headers=headers,
        json={
            "provider": "whatsapp",
            "name": name,
            "source": "whatsapp",
            "channel": "inbound",
            "default_campaign": "Atendimento WhatsApp",
            "routing_config": {},
            "provider_config": {},
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def _configure(
    client: TestClient,
    workspace_id: str,
    source_id: str,
    headers: dict[str, str],
    phone_number_id: str = "PHONE-123",
) -> dict[str, object]:
    response = client.put(
        (
            f"/api/v1/workspaces/{workspace_id}/integrations/"
            f"{source_id}/whatsapp"
        ),
        headers=headers,
        json={
            "phone_number_id": phone_number_id,
            "business_account_id": "WABA-123",
            "access_token": "EAATEST_WHATSAPP_ACCESS_TOKEN_1234567890",
            "default_interest": "Atendimento WhatsApp",
        },
    )
    assert response.status_code == 200
    return response.json()


def _signature(raw: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode("utf-8"), raw, hashlib.sha256
    ).hexdigest()


def test_whatsapp_configuration_encrypts_access_token(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    status = _configure(
        client,
        workspace["public_id"],
        source["public_id"],
        headers,
    )

    assert status["configured"] is True
    assert status["phone_number_id"] == "PHONE-123"
    assert status["business_account_id"] == "WABA-123"
    assert status["webhook_endpoint"] == "/whatsapp/webhook"

    with testing_session() as db:
        stored = db.scalar(select(IntegrationSecret))
        assert stored is not None
        assert "EAATEST_WHATSAPP_ACCESS_TOKEN_1234567890" not in stored.encrypted_payload
        integration = db.scalar(
            select(IntegrationSource).where(
                IntegrationSource.public_id == source["public_id"]
            )
        )
        assert integration is not None
        assert "access_token" not in integration.provider_config


def test_whatsapp_phone_number_id_cannot_be_bound_twice(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    first = _whatsapp_source(client, workspace["public_id"], headers, "Whats A")
    second = _whatsapp_source(client, workspace["public_id"], headers, "Whats B")
    _configure(client, workspace["public_id"], first["public_id"], headers)

    response = client.put(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{second['public_id']}/whatsapp"
        ),
        headers=headers,
        json={
            "phone_number_id": "PHONE-123",
            "business_account_id": "WABA-999",
            "access_token": "EAATEST_OTHER_WHATSAPP_TOKEN_1234567890",
        },
    )
    assert response.status_code == 409


def test_whatsapp_connection_test_uses_graph_client(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    monkeypatch.setattr(
        WhatsAppGraphClient,
        "test_phone_number",
        lambda self, phone_number_id: WhatsAppPhoneInfo(
            phone_number_id=phone_number_id,
            display_phone_number="+55 92 99999-9999",
            verified_name="Nexyra",
            quality_rating="GREEN",
        ),
    )
    response = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/test"
        ),
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["verified_name"] == "Nexyra"
    assert response.json()["quality_rating"] == "GREEN"


def test_whatsapp_business_subscription_marks_source_as_subscribed(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-app-secret-test")
    monkeypatch.setattr(settings, "whatsapp_webhook_verify_token", "verify-wa")
    calls: list[str] = []
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "subscribe_business_account",
        lambda self, business_account_id: calls.append(business_account_id),
    )

    response = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/subscribe"
        ),
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["subscribed"] is True
    assert calls == ["WABA-123"]


def test_whatsapp_webhook_verification_challenge(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "whatsapp_webhook_verify_token",
        "verify-whatsapp-nexyra",
    )

    response = client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-whatsapp-nexyra",
            "hub.challenge": "WA-CHALLENGE-123",
        },
    )
    assert response.status_code == 200
    assert response.text == "WA-CHALLENGE-123"


def test_whatsapp_webhook_creates_lead_message_and_activity(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-app-secret-test")
    monkeypatch.setattr(settings, "whatsapp_webhook_verify_token", "verify-wa")

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "559233333333",
                                "phone_number_id": "PHONE-123",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Cliente WhatsApp"},
                                    "wa_id": "5592999999999",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5592999999999",
                                    "id": "wamid.INBOUND-1",
                                    "timestamp": "1789160000",
                                    "text": {"body": "Quero saber mais sobre o Atlas"},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    response = client.post(
        "/api/v1/whatsapp/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _signature(raw, "wa-app-secret-test"),
        },
    )
    assert response.status_code == 200
    assert response.json()["messages"] == 1
    assert response.json()["created"] == 1

    with testing_session() as db:
        lead = db.scalar(
            select(Lead).where(Lead.normalized_phone == "5592999999999")
        )
        assert lead is not None
        assert lead.name == "Cliente WhatsApp"
        assert lead.source == "whatsapp"
        assert lead.channel == "inbound"
        assert lead.message == "Quero saber mais sobre o Atlas"

        stored = db.scalar(
            select(WhatsAppMessage).where(
                WhatsAppMessage.provider_message_id == "wamid.INBOUND-1"
            )
        )
        assert stored is not None
        assert stored.direction == "inbound"
        assert stored.status == "received"
        assert stored.lead_id == lead.id

        activity = db.scalar(
            select(Activity).where(
                Activity.lead_id == lead.id,
                Activity.activity_type == "whatsapp",
            )
        )
        assert activity is not None
        assert activity.status == "completed"

    repeated = client.post(
        "/api/v1/whatsapp/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _signature(raw, "wa-app-secret-test"),
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["ignored"] >= 1


def test_whatsapp_webhook_rejects_invalid_signature(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-app-secret-test")

    response = client.post(
        "/api/v1/whatsapp/webhook",
        json={"object": "whatsapp_business_account", "entry": []},
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert response.status_code == 401


def test_whatsapp_preview_then_confirmed_send(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    lead_response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=headers,
        json={
            "name": "Lead de Saída",
            "phone": "5592888888888",
            "source": "manual",
            "channel": "crm",
            "priority": "media",
        },
    )
    assert lead_response.status_code == 201

    preview = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/messages/preview"
        ),
        headers=headers,
        json={
            "to": "+55 (92) 88888-8888",
            "text": "Olá! Esta é uma mensagem confirmada.",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["to"] == "5592888888888"

    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "send_text",
        lambda self, *, phone_number_id, to, text: (
            calls.append((phone_number_id, to, text)) or "wamid.OUTBOUND-1"
        ),
    )

    sent = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/messages/send"
        ),
        headers=headers,
        json={
            "to": preview_payload["to"],
            "text": preview_payload["text"],
            "confirmation_token": preview_payload["confirmation_token"],
        },
    )
    assert sent.status_code == 200
    assert sent.json()["provider_message_id"] == "wamid.OUTBOUND-1"
    assert sent.json()["lead_public_id"] == lead_response.json()["public_id"]
    assert calls == [
        (
            "PHONE-123",
            "5592888888888",
            "Olá! Esta é uma mensagem confirmada.",
        )
    ]

    with testing_session() as db:
        stored = db.scalar(
            select(WhatsAppMessage).where(
                WhatsAppMessage.provider_message_id == "wamid.OUTBOUND-1"
            )
        )
        assert stored is not None
        assert stored.direction == "outbound"
        assert stored.status == "sent"


def test_whatsapp_send_rejects_message_changed_after_preview(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    preview = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/messages/preview"
        ),
        headers=headers,
        json={"to": "5592999999999", "text": "Mensagem original"},
    )
    assert preview.status_code == 200

    response = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/messages/send"
        ),
        headers=headers,
        json={
            "to": "5592999999999",
            "text": "Mensagem alterada",
            "confirmation_token": preview.json()["confirmation_token"],
        },
    )
    assert response.status_code == 409


def _approved_template() -> WhatsAppTemplateInfo:
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


def test_whatsapp_templates_list_preview_and_confirmed_send(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    monkeypatch.setattr(
        WhatsAppGraphClient,
        "list_message_templates",
        lambda self, business_account_id, *, limit=100: [_approved_template()],
    )

    listed = client.get(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/templates"
        ),
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "name": "retorno_lead",
            "language": "pt_BR",
            "status": "APPROVED",
            "category": "UTILITY",
            "body_text": "Olá {{1}}, recebemos seu interesse em {{2}}.",
            "parameter_count": 2,
            "supported": True,
            "unsupported_reason": None,
        }
    ]

    preview = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/templates/preview"
        ),
        headers=headers,
        json={
            "to": "+55 (92) 88888-8888",
            "template_name": "retorno_lead",
            "language_code": "pt_BR",
            "parameters": ["Maria", "Radiologia"],
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["to"] == "5592888888888"
    assert preview_payload["rendered_text"] == (
        "Olá Maria, recebemos seu interesse em Radiologia."
    )

    calls: list[tuple[str, str, str, str, list[str]]] = []
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "send_template",
        lambda self, *, phone_number_id, to, template_name, language_code, body_parameters: (
            calls.append(
                (
                    phone_number_id,
                    to,
                    template_name,
                    language_code,
                    body_parameters,
                )
            )
            or "wamid.TEMPLATE-1"
        ),
    )

    sent = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/templates/send"
        ),
        headers=headers,
        json={
            "to": preview_payload["to"],
            "template_name": preview_payload["template_name"],
            "language_code": preview_payload["language_code"],
            "parameters": preview_payload["parameters"],
            "confirmation_token": preview_payload["confirmation_token"],
        },
    )
    assert sent.status_code == 200
    assert sent.json()["provider_message_id"] == "wamid.TEMPLATE-1"
    assert calls == [
        (
            "PHONE-123",
            "5592888888888",
            "retorno_lead",
            "pt_BR",
            ["Maria", "Radiologia"],
        )
    ]

    with testing_session() as db:
        stored = db.scalar(
            select(WhatsAppMessage).where(
                WhatsAppMessage.provider_message_id == "wamid.TEMPLATE-1"
            )
        )
        assert stored is not None
        assert stored.message_type == "template"
        assert stored.body == "Olá Maria, recebemos seu interesse em Radiologia."
        assert stored.metadata_json["template_name"] == "retorno_lead"


def test_whatsapp_template_confirmation_rejects_changed_parameters(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "list_message_templates",
        lambda self, business_account_id, *, limit=100: [_approved_template()],
    )

    preview = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/templates/preview"
        ),
        headers=headers,
        json={
            "to": "5592999999999",
            "template_name": "retorno_lead",
            "language_code": "pt_BR",
            "parameters": ["Maria", "Administração"],
        },
    )
    assert preview.status_code == 200

    changed = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/templates/send"
        ),
        headers=headers,
        json={
            "to": preview.json()["to"],
            "template_name": "retorno_lead",
            "language_code": "pt_BR",
            "parameters": ["Maria", "Radiologia"],
            "confirmation_token": preview.json()["confirmation_token"],
        },
    )
    assert changed.status_code == 409


def test_whatsapp_status_webhook_updates_sent_message(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    preview = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/messages/preview"
        ),
        headers=headers,
        json={"to": "5592777777777", "text": "Mensagem status"},
    )
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "send_text",
        lambda self, *, phone_number_id, to, text: "wamid.STATUS-1",
    )
    sent = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/messages/send"
        ),
        headers=headers,
        json={
            "to": preview.json()["to"],
            "text": preview.json()["text"],
            "confirmation_token": preview.json()["confirmation_token"],
        },
    )
    assert sent.status_code == 200

    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-app-secret-test")
    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "PHONE-123"},
                            "statuses": [
                                {
                                    "id": "wamid.STATUS-1",
                                    "status": "delivered",
                                    "timestamp": "1789160010",
                                    "recipient_id": "5592777777777",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(status_payload, separators=(",", ":")).encode()
    response = client.post(
        "/api/v1/whatsapp/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _signature(raw, "wa-app-secret-test"),
        },
    )
    assert response.status_code == 200
    assert response.json()["statuses"] == 1

    with testing_session() as db:
        stored = db.scalar(
            select(WhatsAppMessage).where(
                WhatsAppMessage.provider_message_id == "wamid.STATUS-1"
            )
        )
        assert stored is not None
        assert stored.status == "delivered"


def test_whatsapp_embedded_signup_connects_coexistence_without_exposing_token(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)

    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_meta_app_id", "1776226846741592")
    monkeypatch.setattr(settings, "whatsapp_embedded_signup_config_id", "CFG-123")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "app-secret-test")

    monkeypatch.setattr(
        WhatsAppGraphClient,
        "exchange_embedded_signup_code",
        lambda **kwargs: "EAATEST_EMBEDDED_SIGNUP_TOKEN_1234567890",
    )
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "list_phone_numbers",
        lambda self, business_account_id: [
            WhatsAppPhoneInfo(
                phone_number_id="PHONE-COEX-1",
                display_phone_number="+55 92 98533-8151",
                verified_name="Nexyra",
                quality_rating="GREEN",
            )
        ],
    )
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "test_phone_number",
        lambda self, phone_number_id: WhatsAppPhoneInfo(
            phone_number_id=phone_number_id,
            display_phone_number="+55 92 98533-8151",
            verified_name="Nexyra",
            quality_rating="GREEN",
        ),
    )
    subscriptions: list[str] = []
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "subscribe_business_account",
        lambda self, business_account_id: subscriptions.append(business_account_id),
    )

    config_response = client.get(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/embedded-signup/config"
        ),
        headers=headers,
    )
    assert config_response.status_code == 200
    assert config_response.json()["enabled"] is True
    assert config_response.json()["feature_type"] == "whatsapp_business_app_onboarding"

    response = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/embedded-signup/complete"
        ),
        headers=headers,
        json={
            "code": "AUTH-CODE-123456",
            "waba_id": "WABA-COEX-1",
            "phone_number_id": None,
            "event": "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING",
            "default_interest": "WhatsApp Business",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is True
    assert payload["coexistence"] is True
    assert payload["phone_number_id"] == "PHONE-COEX-1"
    assert subscriptions == ["WABA-COEX-1"]
    assert "access_token" not in response.text.lower()
    assert "EAATEST_EMBEDDED_SIGNUP_TOKEN" not in response.text

    status = client.get(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp"
        ),
        headers=headers,
    )
    assert status.status_code == 200
    assert status.json()["coexistence"] is True
    assert status.json()["embedded_signup_connected"] is True
    assert status.json()["onboarding_mode"] == "embedded_signup_coexistence"

    with testing_session() as db:
        stored = db.scalar(select(IntegrationSecret))
        assert stored is not None
        assert "EAATEST_EMBEDDED_SIGNUP_TOKEN_1234567890" not in stored.encrypted_payload


def test_whatsapp_embedded_signup_can_require_phone_selection(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)

    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_meta_app_id", "APP-1")
    monkeypatch.setattr(settings, "whatsapp_embedded_signup_config_id", "CFG-1")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "SECRET-1")
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "exchange_embedded_signup_code",
        lambda **kwargs: "EAATEST_MULTI_PHONE_TOKEN_1234567890",
    )
    candidates = [
        WhatsAppPhoneInfo("PHONE-A", "+55 92 90000-0001", "Nexyra A", "GREEN"),
        WhatsAppPhoneInfo("PHONE-B", "+55 92 90000-0002", "Nexyra B", "GREEN"),
    ]
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "list_phone_numbers",
        lambda self, business_account_id: candidates,
    )
    monkeypatch.setattr(
        WhatsAppGraphClient,
        "subscribe_business_account",
        lambda self, business_account_id: None,
    )

    first = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/embedded-signup/complete"
        ),
        headers=headers,
        json={
            "code": "AUTH-CODE-MULTI",
            "waba_id": "WABA-MULTI",
            "event": "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING",
        },
    )
    assert first.status_code == 200
    assert first.json()["selection_required"] is True
    assert len(first.json()["candidates"]) == 2

    monkeypatch.setattr(
        WhatsAppGraphClient,
        "test_phone_number",
        lambda self, phone_number_id: next(
            item for item in candidates if item.phone_number_id == phone_number_id
        ),
    )
    selected = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{source['public_id']}/whatsapp/embedded-signup/select-phone"
        ),
        headers=headers,
        json={"phone_number_id": "PHONE-B"},
    )
    assert selected.status_code == 200
    assert selected.json()["connected"] is True
    assert selected.json()["phone_number_id"] == "PHONE-B"


def test_whatsapp_coexistence_message_echo_is_recorded_as_outbound(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _whatsapp_source(client, workspace["public_id"], headers)
    _configure(client, workspace["public_id"], source["public_id"], headers)

    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_app_secret", "wa-app-secret-test")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-123",
                "changes": [
                    {
                        "field": "smb_message_echoes",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "559233333333",
                                "phone_number_id": "PHONE-123",
                            },
                            "message_echoes": [
                                {
                                    "from": "559233333333",
                                    "to": "5592999999999",
                                    "id": "wamid.ECHO-1",
                                    "timestamp": "1789160100",
                                    "type": "text",
                                    "text": {"body": "Mensagem enviada pelo celular"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    response = client.post(
        "/api/v1/whatsapp/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _signature(raw, "wa-app-secret-test"),
        },
    )
    assert response.status_code == 200
    assert response.json()["echoes"] == 1

    with testing_session() as db:
        stored = db.scalar(
            select(WhatsAppMessage).where(
                WhatsAppMessage.provider_message_id == "wamid.ECHO-1"
            )
        )
        assert stored is not None
        assert stored.direction == "outbound"
        assert stored.status == "sent_from_business_app"
        assert stored.body == "Mensagem enviada pelo celular"
