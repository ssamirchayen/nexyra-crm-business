from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
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
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _workspace(client: TestClient) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Nexyra Consent",
            "slug": "consent-tests",
            "segment": "generic",
        },
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _lead(client: TestClient, workspace_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Maria Consentimento",
            "phone": "5592988887777",
            "email": "maria@example.com",
            "source": "site",
            "channel": "web",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_policy_defaults_and_can_be_updated(client: TestClient) -> None:
    workspace_id = _workspace(client)
    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/communication-policy"
    )
    assert response.status_code == 200
    assert response.json()["enforce_whatsapp_opt_in"] is True
    assert response.json()["enforce_phone_opt_in"] is False

    updated = client.put(
        f"/api/v1/workspaces/{workspace_id}/communication-policy",
        json={
            "enforce_whatsapp_opt_in": True,
            "enforce_email_opt_in": True,
            "enforce_sms_opt_in": True,
            "enforce_phone_opt_in": True,
            "allow_legacy_lead_consent": False,
            "stop_cadence_on_block": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["enforce_phone_opt_in"] is True
    assert updated.json()["allow_legacy_lead_consent"] is False


def test_explicit_channel_opt_out_overrides_legacy_consent(
    client: TestClient,
) -> None:
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)

    initial = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}/communication-consents"
    )
    assert initial.status_code == 200
    whatsapp = next(
        item for item in initial.json()["items"] if item["channel"] == "whatsapp"
    )
    assert whatsapp["allowed"] is True
    assert whatsapp["explicit"] is False

    changed = client.put(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}/communication-consents",
        json={
            "channel": "whatsapp",
            "status": "revoked",
            "source": "cliente",
            "note": "Pediu para não receber mais mensagens.",
        },
    )
    assert changed.status_code == 200, changed.text
    whatsapp = next(
        item for item in changed.json()["items"] if item["channel"] == "whatsapp"
    )
    assert whatsapp["allowed"] is False
    assert whatsapp["explicit"] is True
    assert whatsapp["status"] == "revoked"


def test_global_opt_out_blocks_every_channel_and_disables_legacy_flag(
    client: TestClient,
) -> None:
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}/communication-opt-out",
        json={
            "channel": "all",
            "source": "whatsapp",
            "reason": "Cliente solicitou parar todos os contatos.",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["global_opt_out"] is True
    assert payload["legacy_consent"] is False
    assert all(not item["allowed"] for item in payload["items"])

    refreshed = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/{lead['public_id']}"
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["consent"] is False


def test_whatsapp_preview_is_blocked_after_opt_out(client: TestClient) -> None:
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations",
        json={
            "provider": "whatsapp",
            "name": "WhatsApp Comercial",
            "source": "whatsapp",
            "channel": "inbound",
            "routing_config": {},
            "provider_config": {},
            "active": True,
        },
    )
    assert source.status_code == 201, source.text
    source_id = source.json()["public_id"]
    configured = client.put(
        f"/api/v1/workspaces/{workspace_id}/integrations/"
        f"{source_id}/whatsapp",
        json={
            "phone_number_id": "PHONE-CONSENT",
            "business_account_id": "WABA-CONSENT",
            "access_token": "EAATEST_WHATSAPP_CONSENT_1234567890",
        },
    )
    assert configured.status_code == 200, configured.text

    revoked = client.put(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}/communication-consents",
        json={
            "channel": "whatsapp",
            "status": "revoked",
            "source": "manual",
        },
    )
    assert revoked.status_code == 200

    preview = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations/"
        f"{source_id}/whatsapp/messages/preview",
        json={
            "to": "5592988887777",
            "text": "Mensagem que não deve sair",
        },
    )
    assert preview.status_code == 409
    assert "bloqueada" in str(preview.json()["detail"]).lower()


def test_cadence_enrollment_checks_channel_consent(client: TestClient) -> None:
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)
    revoked = client.put(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}/communication-consents",
        json={
            "channel": "whatsapp",
            "status": "revoked",
            "source": "manual",
        },
    )
    assert revoked.status_code == 200

    cadence = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-cadences",
        json={
            "name": "WhatsApp bloqueado",
            "steps": [
                {
                    "delay_minutes": 0,
                    "action_type": "whatsapp",
                    "title": "Contato WhatsApp",
                    "message_template": "Olá {{lead_name}}",
                }
            ],
        },
    )
    assert cadence.status_code == 201, cadence.text

    enrolled = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-cadence-enrollments",
        json={
            "lead_public_id": lead["public_id"],
            "cadence_public_id": cadence.json()["public_id"],
        },
    )
    assert enrolled.status_code == 422
    assert "bloqueada" in str(enrolled.json()["detail"]).lower()
