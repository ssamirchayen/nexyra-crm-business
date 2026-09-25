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


def _lead(client: TestClient, workspace_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": "Lead Dashboard",
            "phone": "92977778888",
            "source": "instagram",
            "channel": "web",
            "interest": "Radiologia",
            "priority": "alta",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_operational_dashboard_empty_workspace(client: TestClient) -> None:
    workspace = _workspace(client, "ops-empty")
    workspace_id = str(workspace["public_id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/dashboard/operations"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_leads"] == 0
    assert payload["leads_created"] == 0
    assert payload["open_pipeline_value"] == "0.00"
    assert payload["sla"]["total_attention"] == 0
    assert payload["recommendations"]["total"] == 0
    assert payload["whatsapp"]["outbound"] == 0
    assert payload["cadences"]["active_enrollments"] == 0
    assert payload["bottlenecks"] == []


def test_operational_dashboard_combines_live_signals(client: TestClient) -> None:
    workspace = _workspace(client, "ops-live")
    workspace_id = str(workspace["public_id"])
    lead = _lead(client, workspace_id)

    opportunity = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
            "value_amount": "3200.00",
        },
    )
    assert opportunity.status_code == 201

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/dashboard/operations?period_days=30"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_leads"] == 1
    assert payload["leads_created"] == 1
    assert payload["high_priority_leads"] == 1
    assert payload["open_opportunities"] == 1
    assert payload["open_pipeline_value"] == "3200.00"
    assert payload["sla"]["total_attention"] == 1
    assert payload["recommendations"]["total"] == 1
    assert payload["pipeline_stages"]


def test_operational_dashboard_rejects_invalid_owner(client: TestClient) -> None:
    workspace = _workspace(client, "ops-owner")
    workspace_id = str(workspace["public_id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/dashboard/operations"
        "?owner_user_public_id=USR-DOES-NOT-EXIST"
    )

    assert response.status_code == 422


def test_operational_dashboard_validates_period(client: TestClient) -> None:
    workspace = _workspace(client, "ops-period")
    workspace_id = str(workspace["public_id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/dashboard/operations?period_days=6"
    )

    assert response.status_code == 422
