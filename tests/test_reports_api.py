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
            "name": f"Relatórios {slug}",
            "slug": slug,
            "segment": "education",
        },
    )
    assert response.status_code == 201
    return response.json()


def _member(client: TestClient, workspace_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": "Mariana Vendas",
            "email": f"mariana.{workspace_id.lower()}@nexyra.demo",
            "role": "seller",
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
    owner_public_id: str | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": name,
            "phone": phone,
            "source": source,
            "channel": "lead_ads",
            "interest": "Radiologia",
            "owner_user_public_id": owner_public_id,
            "custom_fields": {"curso": "Radiologia"},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_reports_empty_workspace(client: TestClient) -> None:
    workspace = _workspace(client, "empty")
    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/reports/analytics"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_leads"] == 0
    assert payload["open_pipeline_value"] == "0.00"
    assert payload["conversion_rate"] == 0.0
    assert payload["source_performance"] == []
    assert payload["pipeline_stages"] == []
    assert len(payload["revenue_series"]) >= 1


def test_reports_aggregate_sales_sources_pipeline_and_activities(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "complete")
    workspace_id = str(workspace["public_id"])
    seller = _member(client, workspace_id)

    instagram = _lead(
        client,
        workspace_id,
        name="Lead Instagram",
        phone="92911110001",
        source="instagram",
        owner_public_id=str(seller["public_id"]),
    )
    google = _lead(
        client,
        workspace_id,
        name="Lead Google",
        phone="92911110002",
        source="google_ads",
        owner_public_id=str(seller["public_id"]),
    )

    won = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": instagram["public_id"],
            "value_amount": "1800.00",
            "owner_user_public_id": seller["public_id"],
        },
    ).json()
    won_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/{won['public_id']}/won",
        json={},
    )
    assert won_response.status_code == 200

    open_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": google["public_id"],
            "value_amount": "2400.00",
            "owner_user_public_id": seller["public_id"],
        },
    )
    assert open_response.status_code == 201

    activity = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Retorno comercial",
            "lead_public_id": instagram["public_id"],
            "owner_user_public_id": seller["public_id"],
        },
    ).json()
    completed = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/{activity['public_id']}/complete"
    )
    assert completed.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/reports/analytics"
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_leads"] == 2
    assert payload["opportunities_created"] == 2
    assert payload["open_opportunities"] == 1
    assert payload["open_pipeline_value"] == "2400.00"
    assert payload["won_opportunities"] == 1
    assert payload["won_value"] == "1800.00"
    assert payload["conversion_rate"] == 100.0
    assert payload["completed_activities"] == 1
    assert set(payload["available_sources"]) == {"instagram", "google_ads"}

    instagram_stats = next(
        item for item in payload["source_performance"]
        if item["source"] == "instagram"
    )
    assert instagram_stats["leads"] == 1
    assert instagram_stats["won_opportunities"] == 1
    assert instagram_stats["won_value"] == "1800.00"

    seller_stats = payload["member_performance"][0]
    assert seller_stats["public_id"] == seller["public_id"]
    assert seller_stats["won_value"] == "1800.00"
    assert seller_stats["completed_activities"] == 1

    assert payload["pipeline_stages"][0]["opportunities"] == 1
    assert payload["interest_performance"][0]["interest"] == "Radiologia"


def test_reports_filters_by_source_and_owner(client: TestClient) -> None:
    workspace = _workspace(client, "filters")
    workspace_id = str(workspace["public_id"])
    seller = _member(client, workspace_id)

    _lead(
        client,
        workspace_id,
        name="Instagram",
        phone="92922220001",
        source="instagram",
        owner_public_id=str(seller["public_id"]),
    )
    _lead(
        client,
        workspace_id,
        name="Google",
        phone="92922220002",
        source="google_ads",
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/reports/analytics",
        params={
            "source": "instagram",
            "owner_user_public_id": seller["public_id"],
            "period_days": 90,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period_days"] == 90
    assert payload["source_filter"] == "instagram"
    assert payload["owner_user_public_id_filter"] == seller["public_id"]
    assert payload["total_leads"] == 1
    assert len(payload["member_performance"]) == 1


def test_reports_reject_owner_from_another_workspace(client: TestClient) -> None:
    first = _workspace(client, "owner-a")
    second = _workspace(client, "owner-b")
    second_member = _member(client, str(second["public_id"]))

    response = client.get(
        f"/api/v1/workspaces/{first['public_id']}/reports/analytics",
        params={"owner_user_public_id": second_member["public_id"]},
    )

    assert response.status_code == 422
