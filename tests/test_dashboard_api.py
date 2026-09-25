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


def _lead(
    client: TestClient,
    workspace_id: str,
    *,
    name: str,
    phone: str,
    source: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": name,
            "phone": phone,
            "source": source,
            "channel": "web",
            "interest": "Radiologia",
            "custom_fields": {"curso": "Radiologia"},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_dashboard_summary_uses_real_workspace_data(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "dashboard-real")
    workspace_id = str(workspace["public_id"])

    first_lead = _lead(
        client,
        workspace_id,
        name="Mariana Lopes",
        phone="92911112222",
        source="instagram",
    )
    second_lead = _lead(
        client,
        workspace_id,
        name="Rafael Costa",
        phone="92933334444",
        source="google_ads",
    )

    won_opportunity = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": first_lead["public_id"],
            "value_amount": "1500.00",
        },
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{won_opportunity['public_id']}/won",
        json={},
    )

    client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": second_lead["public_id"],
            "value_amount": "2300.00",
        },
    )

    activity = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "whatsapp",
            "title": "Retornar contato",
            "lead_public_id": second_lead["public_id"],
            "due_at": "2030-01-10T15:00:00Z",
        },
    )
    assert activity.status_code == 201

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/dashboard/summary"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["workspace_public_id"] == workspace_id
    assert payload["leads_in_period"] == 2
    assert payload["open_opportunities"] == 1
    assert payload["open_pipeline_value"] == "2300.00"
    assert payload["won_opportunities_in_period"] == 1
    assert payload["won_value_in_period"] == "1500.00"
    assert payload["conversion_rate"] == 100.0
    assert len(payload["recent_leads"]) == 2
    assert len(payload["upcoming_activities"]) == 1

    sources = {
        item["source"]: item["count"]
        for item in payload["source_distribution"]
    }
    assert sources == {"instagram": 1, "google_ads": 1}


def test_dashboard_empty_workspace_returns_zero_metrics(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "dashboard-empty")
    workspace_id = str(workspace["public_id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/dashboard/summary"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["leads_in_period"] == 0
    assert payload["open_pipeline_value"] == "0.00"
    assert payload["conversion_rate"] == 0.0
    assert payload["source_distribution"] == []
    assert payload["recent_leads"] == []
    assert payload["upcoming_activities"] == []
    assert len(payload["revenue_series"]) == 4


def test_dashboard_isolated_by_workspace(client: TestClient) -> None:
    first = _workspace(client, "dashboard-a")
    second = _workspace(client, "dashboard-b")

    first_id = str(first["public_id"])
    second_id = str(second["public_id"])

    _lead(
        client,
        first_id,
        name="Lead somente A",
        phone="92955556666",
        source="instagram",
    )

    response = client.get(
        f"/api/v1/workspaces/{second_id}/dashboard/summary"
    )

    assert response.status_code == 200
    assert response.json()["leads_in_period"] == 0


def test_frontend_origin_is_allowed_by_cors(client: TestClient) -> None:
    response = client.options(
        "/api/v1/workspaces",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://127.0.0.1:5173"
    )
