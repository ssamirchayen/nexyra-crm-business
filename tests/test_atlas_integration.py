from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

TOKEN = "dev-nexyra-atlas-token"


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


def _workspace(client: TestClient, slug: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": f"Empresa {slug}",
            "slug": slug,
            "segment": "education",
        },
    )
    assert response.status_code == 201
    return response.json()


def _member(
    client: TestClient,
    workspace_id: str,
    *,
    email: str,
    role: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": f"Usuário {role}",
            "email": email,
            "role": role,
        },
    )
    assert response.status_code == 201
    return response.json()


def _headers(user_public_id: str) -> dict[str, str]:
    return {
        "X-Nexyra-Integration-Token": TOKEN,
        "X-Nexyra-Actor-User": user_public_id,
    }


def _lead(
    client: TestClient,
    workspace_id: str,
    phone: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Lead Integração",
            "phone": phone,
            "source": "instagram",
            "channel": "lead_ads",
            "campaign": "radiologia-setembro",
            "interest": "Radiologia",
            "custom_fields": {"curso": "Radiologia"},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_atlas_contract_health(client: TestClient) -> None:
    response = client.get("/api/v1/integrations/atlas/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["crm_version"] == "1.0.0"
    assert payload["contract_version"] == "1.0"
    assert payload["contract_name"] == "nexyra-crm-atlas"


def test_capabilities_require_integration_token(
    client: TestClient,
) -> None:
    denied = client.get(
        "/api/v1/integrations/atlas/capabilities",
        headers={"X-Nexyra-Integration-Token": "wrong"},
    )
    allowed = client.get(
        "/api/v1/integrations/atlas/capabilities",
        headers={"X-Nexyra-Integration-Token": TOKEN},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert "lead_source_tracking" in allowed.json()["capabilities"]
    assert "lead.update" in allowed.json()["supported_actions"]


def test_workspace_context_tracks_instagram_source(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "atlas-context")
    workspace_id = str(workspace["public_id"])

    seller = _member(
        client,
        workspace_id,
        email="seller-context@nexyra.demo",
        role="seller",
    )
    _lead(client, workspace_id, "92930000001")

    response = client.get(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/context",
        headers=_headers(str(seller["public_id"])),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actor"]["role"] == "seller"
    assert payload["counts"]["leads"] == 1
    assert payload["lead_sources"] == [
        {
            "source": "instagram",
            "channel": "lead_ads",
            "lead_count": 1,
        }
    ]


def test_operator_cannot_use_atlas_context(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "atlas-operator")
    workspace_id = str(workspace["public_id"])
    operator = _member(
        client,
        workspace_id,
        email="operator@nexyra.demo",
        role="operator",
    )

    response = client.get(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/context",
        headers=_headers(str(operator["public_id"])),
    )

    assert response.status_code == 403


def test_lead_intake_is_ready_for_lead_hub(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "atlas-intake")
    workspace_id = str(workspace["public_id"])
    manager = _member(
        client,
        workspace_id,
        email="manager-intake@nexyra.demo",
        role="manager",
    )
    headers = _headers(str(manager["public_id"]))

    payload = {
        "name": "Lead Meta",
        "phone": "92930000002",
        "source": "instagram",
        "channel": "lead_ads",
        "campaign": "campanha-meta",
        "interest": "Radiologia",
        "custom_fields": {"curso": "Radiologia"},
    }

    first = client.post(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/lead-intake",
        headers=headers,
        json=payload,
    )
    second = client.post(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/lead-intake",
        headers=headers,
        json={**payload, "name": "Lead Meta Atualizado"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["action"] == "created"
    assert second.json()["action"] == "duplicate_updated"
    assert (
        first.json()["lead"]["public_id"]
        == second.json()["lead"]["public_id"]
    )

    audit = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit",
        params={"action": "integration.lead_intake"},
    )
    assert audit.status_code == 200
    assert len(audit.json()) == 2
    assert audit.json()[0]["actor_type"] == "integration"


def test_preview_does_not_execute_action(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "atlas-preview")
    workspace_id = str(workspace["public_id"])
    seller = _member(
        client,
        workspace_id,
        email="seller-preview@nexyra.demo",
        role="seller",
    )
    lead = _lead(client, workspace_id, "92930000003")

    response = client.post(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/actions/preview",
        headers=_headers(str(seller["public_id"])),
        json={
            "action": "lead.update",
            "target_public_id": lead["public_id"],
            "payload": {"priority": "alta"},
            "reason": "Lead com alta intenção.",
        },
    )

    assert response.status_code == 200
    assert response.json()["confirmation_required"] is True

    fetched = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}"
    )
    assert fetched.json()["priority"] == "media"


def test_seller_cannot_execute_atlas_action(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "atlas-seller-execute")
    workspace_id = str(workspace["public_id"])
    seller = _member(
        client,
        workspace_id,
        email="seller-execute@nexyra.demo",
        role="seller",
    )
    lead = _lead(client, workspace_id, "92930000004")

    response = client.post(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/actions/execute",
        headers=_headers(str(seller["public_id"])),
        json={
            "action": "lead.update",
            "target_public_id": lead["public_id"],
            "payload": {"priority": "alta"},
            "confirmed": True,
        },
    )

    assert response.status_code == 403


def test_execute_requires_confirmation_and_is_audited(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "atlas-execute")
    workspace_id = str(workspace["public_id"])
    manager = _member(
        client,
        workspace_id,
        email="manager-execute@nexyra.demo",
        role="manager",
    )
    lead = _lead(client, workspace_id, "92930000005")
    headers = _headers(str(manager["public_id"]))

    unconfirmed = client.post(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/actions/execute",
        headers=headers,
        json={
            "action": "lead.update",
            "target_public_id": lead["public_id"],
            "payload": {"priority": "urgente"},
            "confirmed": False,
        },
    )

    assert unconfirmed.status_code == 409

    executed = client.post(
        f"/api/v1/integrations/atlas/workspaces/"
        f"{workspace_id}/actions/execute",
        headers=headers,
        json={
            "action": "lead.update",
            "target_public_id": lead["public_id"],
            "payload": {"priority": "urgente"},
            "reason": "Solicitado pelo gerente.",
            "confirmed": True,
        },
    )

    assert executed.status_code == 200
    assert executed.json()["executed"] is True
    assert executed.json()["result"]["priority"] == "urgente"

    audit = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit",
        params={"action": "atlas.action.executed"},
    )
    assert audit.status_code == 200
    assert len(audit.json()) == 1
    assert audit.json()[0]["actor_type"] == "atlas"
    assert (
        audit.json()[0]["actor_user_public_id"]
        == manager["public_id"]
    )
