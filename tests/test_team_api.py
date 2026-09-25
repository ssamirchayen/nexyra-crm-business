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


def _workspace(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Equipe Demo",
            "slug": "equipe-demo",
            "segment": "generic",
        },
    )
    assert response.status_code == 201
    return response.json()


def _member(
    client: TestClient,
    workspace_id: str,
    *,
    name: str,
    email: str,
    role: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"name": name, "email": email, "role": role},
    )
    assert response.status_code == 201
    return response.json()


def test_team_summary_empty_workspace(client: TestClient) -> None:
    workspace = _workspace(client)
    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/team/summary"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_members"] == 0
    assert payload["active_members"] == 0
    assert payload["total_won_value"] == "0.00"
    assert payload["members"] == []


def test_team_summary_aggregates_member_performance(client: TestClient) -> None:
    workspace = _workspace(client)
    workspace_id = str(workspace["public_id"])
    seller = _member(
        client,
        workspace_id,
        name="Mariana Lopes",
        email="mariana.team@nexyra.demo",
        role="seller",
    )
    _member(
        client,
        workspace_id,
        name="Carlos Gestor",
        email="carlos.team@nexyra.demo",
        role="manager",
    )

    lead_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Lead da Mariana",
            "source": "instagram",
            "channel": "lead_ads",
            "owner_user_public_id": seller["public_id"],
        },
    )
    assert lead_response.status_code == 201
    lead = lead_response.json()

    won_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
            "title": "Matrícula Radiologia",
            "value_amount": "1500.00",
            "owner_user_public_id": seller["public_id"],
        },
    )
    assert won_response.status_code == 201
    won = won_response.json()

    mark_won = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{won['public_id']}/won",
        json={},
    )
    assert mark_won.status_code == 200

    open_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
            "title": "Nova negociação",
            "value_amount": "900.00",
            "owner_user_public_id": seller["public_id"],
        },
    )
    assert open_response.status_code == 201

    activity_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Retorno atrasado",
            "owner_user_public_id": seller["public_id"],
            "lead_public_id": lead["public_id"],
            "due_at": "2020-01-01T12:00:00Z",
        },
    )
    assert activity_response.status_code == 201

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/team/summary"
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_members"] == 2
    assert payload["active_members"] == 2
    assert payload["sellers"] == 1
    assert payload["managers"] == 1
    assert payload["total_assigned_leads"] == 1
    assert payload["total_open_opportunities"] == 1
    assert payload["total_won_value"] == "1500.00"

    seller_stats = next(
        item for item in payload["members"] if item["public_id"] == seller["public_id"]
    )
    assert seller_stats["assigned_leads"] == 1
    assert seller_stats["open_opportunities"] == 1
    assert seller_stats["won_opportunities"] == 1
    assert seller_stats["lost_opportunities"] == 0
    assert seller_stats["conversion_rate"] == 100.0
    assert seller_stats["won_value"] == "1500.00"
    assert seller_stats["pending_activities"] == 1
    assert seller_stats["overdue_activities"] == 1
