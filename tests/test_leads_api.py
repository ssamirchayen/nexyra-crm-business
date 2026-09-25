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


def _workspace(
    client: TestClient,
    slug: str,
    segment: str = "generic",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": f"Empresa {slug}",
            "slug": slug,
            "segment": segment,
        },
    )

    assert response.status_code == 201
    return response.json()


def _member(
    client: TestClient,
    workspace_id: str,
    email: str,
    role: str = "seller",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": "Vendedor Demo",
            "email": email,
            "role": role,
        },
    )

    assert response.status_code == 201
    return response.json()


def test_create_education_lead_with_owner(
    client: TestClient,
) -> None:
    workspace = _workspace(
        client,
        "escola-demo",
        "education",
    )
    workspace_id = str(workspace["public_id"])

    seller = _member(
        client,
        workspace_id,
        "seller@escola.demo",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Mariana Lopes",
            "phone": "(92) 98800-1101",
            "email": "mariana@example.com",
            "interest": "Radiologia",
            "source": "instagram",
            "channel": "social",
            "campaign": "radiologia-setembro",
            "priority": "alta",
            "owner_user_public_id": seller["public_id"],
            "custom_fields": {
                "curso": "Radiologia",
                "turno": "noturno",
            },
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["public_id"].startswith("LEAD-")
    assert payload["status"] == "novo"
    assert payload["priority"] == "alta"
    assert payload["owner_user_public_id"] == seller["public_id"]
    assert payload["custom_fields"]["curso"] == "Radiologia"


def test_duplicate_is_blocked_inside_same_workspace(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "loja-duplicada", "retail")
    workspace_id = str(workspace["public_id"])

    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Rafael Costa",
            "phone": "92999990000",
            "interest": "Notebook",
        },
    )

    second = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Rafael Outro",
            "phone": "(92) 99999-0000",
            "interest": "Monitor",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409

    detail = second.json()["detail"]

    assert detail["existing_lead_public_id"] == first.json()["public_id"]


def test_same_identity_can_exist_in_different_workspaces(
    client: TestClient,
) -> None:
    first_workspace = _workspace(client, "empresa-lead-a")
    second_workspace = _workspace(client, "empresa-lead-b")

    payload = {
        "name": "Ana Beatriz",
        "phone": "92988887777",
    }

    first = client.post(
        f"/api/v1/workspaces/{first_workspace['public_id']}/leads",
        json=payload,
    )
    second = client.post(
        f"/api/v1/workspaces/{second_workspace['public_id']}/leads",
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["public_id"] != second.json()["public_id"]


def test_custom_fields_follow_workspace_segment(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "auto-fields", "automotive")
    workspace_id = str(workspace["public_id"])

    valid = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Lucas Pereira",
            "phone": "92911112222",
            "custom_fields": {
                "veiculo": "Onix",
                "ano": 2025,
            },
        },
    )

    invalid = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Bianca Souza",
            "phone": "92911113333",
            "custom_fields": {
                "curso": "Radiologia",
            },
        },
    )

    assert valid.status_code == 201
    assert invalid.status_code == 422


def test_status_must_belong_to_pipeline(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "pipeline-lead", "education")
    workspace_id = str(workspace["public_id"])

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Lead Status",
            "phone": "92922223333",
            "status": "test_drive",
        },
    )

    assert response.status_code == 422


def test_owner_must_belong_to_same_workspace(
    client: TestClient,
) -> None:
    first = _workspace(client, "owner-a")
    second = _workspace(client, "owner-b")

    second_id = str(second["public_id"])

    seller = _member(
        client,
        str(first["public_id"]),
        "owner@empresa.demo",
    )

    response = client.post(
        f"/api/v1/workspaces/{second_id}/leads",
        json={
            "name": "Lead Owner",
            "phone": "92933334444",
            "owner_user_public_id": seller["public_id"],
        },
    )

    assert response.status_code == 422


def test_intake_updates_duplicate_instead_of_creating_new(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "intake-demo", "retail")
    workspace_id = str(workspace["public_id"])

    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/intake",
        json={
            "name": "Cliente Intake",
            "phone": "92944445555",
            "interest": "Notebook",
            "priority": "media",
            "custom_fields": {
                "produto": "Notebook",
            },
        },
    )

    second = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/intake",
        json={
            "name": "Cliente Intake Atualizado",
            "phone": "(92) 94444-5555",
            "interest": "Notebook Gamer",
            "priority": "alta",
            "custom_fields": {
                "categoria": "Informática",
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_payload = first.json()
    second_payload = second.json()

    assert first_payload["action"] == "created"
    assert second_payload["action"] == "duplicate_updated"

    assert (
        first_payload["lead"]["public_id"]
        == second_payload["lead"]["public_id"]
    )
    assert second_payload["lead"]["priority"] == "alta"
    assert second_payload["lead"]["interest"] == "Notebook Gamer"
    assert second_payload["lead"]["custom_fields"]["produto"] == "Notebook"
    assert (
        second_payload["lead"]["custom_fields"]["categoria"]
        == "Informática"
    )


def test_update_list_get_and_deactivate_lead(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "crud-lead", "services")
    workspace_id = str(workspace["public_id"])

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Cliente Serviço",
            "phone": "92955556666",
            "interest": "Consultoria",
            "custom_fields": {
                "servico": "Consultoria",
            },
        },
    ).json()

    lead_id = created["public_id"]

    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads"
    )
    fetched = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/{lead_id}"
    )
    updated = client.patch(
        f"/api/v1/workspaces/{workspace_id}/leads/{lead_id}",
        json={
            "status": "qualificado",
            "priority": "urgente",
        },
    )
    deactivated = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead_id}/deactivate"
    )

    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert fetched.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["status"] == "qualificado"
    assert updated.json()["priority"] == "urgente"
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False
