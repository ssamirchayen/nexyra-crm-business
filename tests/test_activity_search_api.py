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


def _workspace(client: TestClient, slug: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={"name": f"Empresa {slug}", "slug": slug, "segment": "education"},
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _member(client: TestClient, workspace_id: str, suffix: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": f"Vendedor {suffix}",
            "email": f"{suffix}@activities.demo",
            "role": "seller",
        },
    )
    assert response.status_code == 201
    return response.json()


def _lead(client: TestClient, workspace_id: str, suffix: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": f"Lead {suffix}",
            "phone": f"9298800{suffix[-4:].zfill(4)}",
            "interest": "Radiologia",
            "custom_fields": {"curso": "Radiologia"},
        },
    )
    assert response.status_code == 201
    return response.json()


def _opportunity(client: TestClient, workspace_id: str, lead_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead_id,
            "title": "Matrícula Radiologia",
            "value_amount": "1500.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_activity_search_returns_context_names(client: TestClient) -> None:
    workspace_id = _workspace(client, "activity-search-context")
    member = _member(client, workspace_id, "context")
    lead = _lead(client, workspace_id, "1001")
    opportunity = _opportunity(client, workspace_id, str(lead["public_id"]))

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "meeting",
            "title": "Reunião de matrícula",
            "opportunity_public_id": opportunity["public_id"],
            "owner_user_public_id": member["public_id"],
            "due_at": "2035-01-10T14:00:00Z",
        },
    )
    assert created.status_code == 201

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/activities/search?q=matrícula"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["lead_name"] == "Lead 1001"
    assert item["opportunity_title"] == "Matrícula Radiologia"
    assert item["owner_name"] == "Vendedor context"
    assert item["created_at"] is not None
    assert item["updated_at"] is not None


def test_activity_search_filters_status_type_and_owner(client: TestClient) -> None:
    workspace_id = _workspace(client, "activity-search-filters")
    member = _member(client, workspace_id, "filters")
    lead = _lead(client, workspace_id, "1002")

    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "whatsapp",
            "title": "Retorno WhatsApp",
            "lead_public_id": lead["public_id"],
            "owner_user_public_id": member["public_id"],
        },
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "call",
            "title": "Ligação sem responsável",
            "lead_public_id": lead["public_id"],
        },
    )
    client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/{first['public_id']}/complete"
    )

    completed = client.get(
        f"/api/v1/workspaces/{workspace_id}/activities/search",
        params={
            "status": "completed",
            "activity_type": "whatsapp",
            "owner_user_public_id": member["public_id"],
        },
    )
    assert completed.status_code == 200
    assert completed.json()["total"] == 1

    unassigned = client.get(
        f"/api/v1/workspaces/{workspace_id}/activities/search?unassigned=true"
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["total"] == 1
    assert unassigned.json()["items"][0]["activity_type"] == "call"


def test_activity_search_overdue_filter(client: TestClient) -> None:
    workspace_id = _workspace(client, "activity-search-overdue")
    lead = _lead(client, workspace_id, "1003")

    client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Atrasado",
            "lead_public_id": lead["public_id"],
            "due_at": "2020-01-01T10:00:00Z",
        },
    )
    client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Futuro",
            "lead_public_id": lead["public_id"],
            "due_at": "2038-01-01T10:00:00Z",
        },
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/activities/search?overdue=true"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Atrasado"
    assert payload["items"][0]["overdue"] is True


def test_activity_search_paginates_and_isolates_workspace(client: TestClient) -> None:
    first_id = _workspace(client, "activity-page-a")
    second_id = _workspace(client, "activity-page-b")

    for index in range(3):
        response = client.post(
            f"/api/v1/workspaces/{first_id}/activities",
            json={"activity_type": "task", "title": f"Tarefa {index}"},
        )
        assert response.status_code == 201

    other = client.post(
        f"/api/v1/workspaces/{second_id}/activities",
        json={"activity_type": "task", "title": "Tarefa externa"},
    )
    assert other.status_code == 201

    response = client.get(
        f"/api/v1/workspaces/{first_id}/activities/search?page=2&page_size=2"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 2
    assert payload["total_pages"] == 2
    assert len(payload["items"]) == 1


def test_activity_search_validates_page_size(client: TestClient) -> None:
    workspace_id = _workspace(client, "activity-page-limit")
    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/activities/search?page_size=101"
    )
    assert response.status_code == 422
