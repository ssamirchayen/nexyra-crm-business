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
    email: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": "Vendedor Demo",
            "email": email,
            "role": "seller",
        },
    )
    assert response.status_code == 201
    return response.json()


def _lead(
    client: TestClient,
    workspace_id: str,
    phone: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Lead Demo",
            "phone": phone,
            "interest": "Radiologia",
            "custom_fields": {
                "curso": "Radiologia",
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def _opportunity(
    client: TestClient,
    workspace_id: str,
    lead_id: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead_id,
            "value_amount": "1200.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_activity_types_available(client: TestClient) -> None:
    response = client.get("/api/v1/activity-types")

    assert response.status_code == 200

    types = set(response.json())

    assert {
        "call",
        "whatsapp",
        "email",
        "meeting",
        "task",
        "follow_up",
        "note",
    } == types


def test_create_whatsapp_follow_up_for_lead(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "activity-lead")
    workspace_id = str(workspace["public_id"])

    seller = _member(
        client,
        workspace_id,
        "seller-activity@nexyra.demo",
    )
    lead = _lead(
        client,
        workspace_id,
        "92910000001",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "whatsapp",
            "title": "Retornar contato",
            "description": "Enviar condições comerciais.",
            "lead_public_id": lead["public_id"],
            "owner_user_public_id": seller["public_id"],
            "due_at": "2030-01-10T15:00:00Z",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["public_id"].startswith("ACT-")
    assert payload["activity_type"] == "whatsapp"
    assert payload["status"] == "pending"
    assert payload["lead_public_id"] == lead["public_id"]
    assert payload["owner_user_public_id"] == seller["public_id"]


def test_opportunity_activity_infers_linked_lead(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "activity-opportunity")
    workspace_id = str(workspace["public_id"])

    lead = _lead(
        client,
        workspace_id,
        "92910000002",
    )
    opportunity = _opportunity(
        client,
        workspace_id,
        str(lead["public_id"]),
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "meeting",
            "title": "Reunião de fechamento",
            "opportunity_public_id": opportunity["public_id"],
            "due_at": "2030-01-11T14:00:00Z",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["opportunity_public_id"] == opportunity["public_id"]
    assert payload["lead_public_id"] == lead["public_id"]


def test_activity_history_by_lead_and_opportunity(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "activity-history")
    workspace_id = str(workspace["public_id"])

    lead = _lead(
        client,
        workspace_id,
        "92910000003",
    )
    opportunity = _opportunity(
        client,
        workspace_id,
        str(lead["public_id"]),
    )

    client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "call",
            "title": "Ligação inicial",
            "lead_public_id": lead["public_id"],
        },
    )

    client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "email",
            "title": "Enviar proposta",
            "opportunity_public_id": opportunity["public_id"],
        },
    )

    lead_history = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}/activities"
    )
    opportunity_history = client.get(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity['public_id']}/activities"
    )

    assert lead_history.status_code == 200
    assert len(lead_history.json()) == 2

    assert opportunity_history.status_code == 200
    assert len(opportunity_history.json()) == 1
    assert opportunity_history.json()[0]["activity_type"] == "email"


def test_complete_and_cancel_activities(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "activity-state")
    workspace_id = str(workspace["public_id"])
    lead = _lead(
        client,
        workspace_id,
        "92910000004",
    )

    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "task",
            "title": "Preparar proposta",
            "lead_public_id": lead["public_id"],
        },
    ).json()

    second = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Retornar amanhã",
            "lead_public_id": lead["public_id"],
        },
    ).json()

    completed = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/"
        f"{first['public_id']}/complete"
    )
    cancelled = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/"
        f"{second['public_id']}/cancel"
    )

    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None


def test_completed_activity_cannot_be_completed_again(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "activity-repeat")
    workspace_id = str(workspace["public_id"])
    lead = _lead(
        client,
        workspace_id,
        "92910000005",
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "call",
            "title": "Contato",
            "lead_public_id": lead["public_id"],
        },
    ).json()

    activity_id = str(created["public_id"])

    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/"
        f"{activity_id}/complete"
    )
    second = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/"
        f"{activity_id}/complete"
    )

    assert first.status_code == 200
    assert second.status_code == 422


def test_pending_queue_marks_overdue(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "activity-pending")
    workspace_id = str(workspace["public_id"])
    lead = _lead(
        client,
        workspace_id,
        "92910000006",
    )

    overdue = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Retorno atrasado",
            "lead_public_id": lead["public_id"],
            "due_at": "2020-01-01T12:00:00Z",
        },
    )
    future = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "meeting",
            "title": "Reunião futura",
            "lead_public_id": lead["public_id"],
            "due_at": "2035-01-01T12:00:00Z",
        },
    )

    assert overdue.status_code == 201
    assert future.status_code == 201

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/follow-ups/pending"
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 2

    by_title = {item["title"]: item for item in payload}

    assert by_title["Retorno atrasado"]["overdue"] is True
    assert by_title["Reunião futura"]["overdue"] is False


def test_owner_must_belong_to_same_workspace(
    client: TestClient,
) -> None:
    first = _workspace(client, "activity-owner-a")
    second = _workspace(client, "activity-owner-b")

    first_id = str(first["public_id"])
    second_id = str(second["public_id"])

    seller = _member(
        client,
        first_id,
        "seller-cross@nexyra.demo",
    )
    lead = _lead(
        client,
        second_id,
        "92910000007",
    )

    response = client.post(
        f"/api/v1/workspaces/{second_id}/activities",
        json={
            "activity_type": "task",
            "title": "Tarefa cruzada",
            "lead_public_id": lead["public_id"],
            "owner_user_public_id": seller["public_id"],
        },
    )

    assert response.status_code == 422


def test_activity_is_isolated_by_workspace(
    client: TestClient,
) -> None:
    first = _workspace(client, "activity-isolated-a")
    second = _workspace(client, "activity-isolated-b")

    first_id = str(first["public_id"])
    second_id = str(second["public_id"])

    lead = _lead(
        client,
        first_id,
        "92910000008",
    )

    created = client.post(
        f"/api/v1/workspaces/{first_id}/activities",
        json={
            "activity_type": "note",
            "title": "Observação interna",
            "lead_public_id": lead["public_id"],
        },
    ).json()

    response = client.get(
        f"/api/v1/workspaces/{second_id}/activities/"
        f"{created['public_id']}"
    )

    assert response.status_code == 404


def test_workspace_level_task_is_allowed(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "activity-general")
    workspace_id = str(workspace["public_id"])

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "task",
            "title": "Revisar metas comerciais",
            "due_at": "2030-02-01T12:00:00Z",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["lead_public_id"] is None
    assert payload["opportunity_public_id"] is None
    assert payload["status"] == "pending"
