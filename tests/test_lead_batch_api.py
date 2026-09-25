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
            "name": "Nexyra Lote",
            "slug": "nexyra-lote",
            "segment": "education",
        },
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _lead(client: TestClient, workspace_id: str, index: int) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": f"Lead {index}",
            "phone": f"92990000{index:02d}",
            "interest": "Radiologia",
            "source": "site",
            "channel": "web",
            "priority": "media",
            "custom_fields": {"curso": "Radiologia"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_batch_preview_does_not_persist(client: TestClient) -> None:
    workspace_id = _workspace(client)
    first = _lead(client, workspace_id, 1)
    second = _lead(client, workspace_id, 2)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/batch",
        json={
            "lead_public_ids": [first["public_id"], second["public_id"]],
            "priority": "alta",
            "dry_run": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["changed"] == 2
    assert all(item["after_priority"] == "alta" for item in payload["items"])

    stored = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/{first['public_id']}"
    ).json()
    assert stored["priority"] == "media"


def test_batch_execute_updates_multiple_fields(client: TestClient) -> None:
    workspace_id = _workspace(client)
    first = _lead(client, workspace_id, 1)
    second = _lead(client, workspace_id, 2)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/batch",
        json={
            "lead_public_ids": [first["public_id"], second["public_id"]],
            "status": "contatado",
            "priority": "urgente",
            "active": False,
            "dry_run": False,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["changed"] == 2
    assert payload["unchanged"] == 0

    for lead in (first, second):
        stored = client.get(
            f"/api/v1/workspaces/{workspace_id}/leads/{lead['public_id']}"
        ).json()
        assert stored["status"] == "contatado"
        assert stored["priority"] == "urgente"
        assert stored["active"] is False


def test_batch_can_assign_owner(client: TestClient) -> None:
    workspace_id = _workspace(client)
    member = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": "Consultor",
            "email": "consultor-batch@nexyra.local",
            "role": "seller",
        },
    )
    assert member.status_code == 201
    seller_id = member.json()["public_id"]
    lead = _lead(client, workspace_id, 1)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/batch",
        json={
            "lead_public_ids": [lead["public_id"]],
            "owner_mode": "assign",
            "owner_user_public_id": seller_id,
            "dry_run": False,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["after_owner_user_public_id"] == seller_id


def test_batch_rejects_invalid_pipeline_status(client: TestClient) -> None:
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id, 1)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/batch",
        json={
            "lead_public_ids": [lead["public_id"]],
            "status": "status_inexistente",
            "dry_run": True,
        },
    )
    assert response.status_code == 422
