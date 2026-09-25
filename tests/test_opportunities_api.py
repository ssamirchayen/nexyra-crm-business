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
    segment: str = "education",
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
    owner_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Lead Demo",
        "phone": phone,
        "interest": "Radiologia",
        "custom_fields": {
            "curso": "Radiologia",
        },
    }

    if owner_id is not None:
        payload["owner_user_public_id"] = owner_id

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json=payload,
    )

    assert response.status_code == 201
    return response.json()


def test_create_opportunity_inherits_lead_owner(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "opp-owner")
    workspace_id = str(workspace["public_id"])

    seller = _member(
        client,
        workspace_id,
        "seller-owner@nexyra.demo",
    )
    lead = _lead(
        client,
        workspace_id,
        "92911110001",
        str(seller["public_id"]),
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
            "value_amount": "1500.00",
            "currency": "BRL",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["public_id"].startswith("OPP-")
    assert payload["lead_public_id"] == lead["public_id"]
    assert payload["owner_user_public_id"] == seller["public_id"]
    assert payload["title"] == "Radiologia"
    assert payload["stage"] == "novo"
    assert payload["status"] == "open"


def test_move_opportunity_records_history(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "opp-history")
    workspace_id = str(workspace["public_id"])

    seller = _member(
        client,
        workspace_id,
        "seller-history@nexyra.demo",
    )
    lead = _lead(
        client,
        workspace_id,
        "92911110002",
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
            "value_amount": "2000.00",
        },
    ).json()

    opportunity_id = str(created["public_id"])

    moved = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity_id}/move",
        json={
            "to_stage": "contatado",
            "changed_by_user_public_id": seller["public_id"],
            "note": "Primeiro contato realizado.",
        },
    )

    assert moved.status_code == 200
    assert moved.json()["stage"] == "contatado"

    history = client.get(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity_id}/history"
    )

    assert history.status_code == 200

    payload = history.json()

    assert len(payload) == 2
    assert payload[0]["from_stage"] is None
    assert payload[0]["to_stage"] == "novo"
    assert payload[1]["from_stage"] == "novo"
    assert payload[1]["to_stage"] == "contatado"
    assert (
        payload[1]["changed_by_user_public_id"]
        == seller["public_id"]
    )


def test_invalid_pipeline_stage_returns_422(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "opp-stage")
    workspace_id = str(workspace["public_id"])
    lead = _lead(
        client,
        workspace_id,
        "92911110003",
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
        },
    ).json()

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{created['public_id']}/move",
        json={
            "to_stage": "test_drive",
        },
    )

    assert response.status_code == 422


def test_mark_won_and_lost_with_conversion_metrics(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "opp-metrics")
    workspace_id = str(workspace["public_id"])

    lead_won = _lead(
        client,
        workspace_id,
        "92911110004",
    )
    lead_lost = _lead(
        client,
        workspace_id,
        "92911110005",
    )

    won_opp = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead_won["public_id"],
            "value_amount": "1000.00",
        },
    ).json()

    lost_opp = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead_lost["public_id"],
            "value_amount": "800.00",
        },
    ).json()

    won = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{won_opp['public_id']}/won",
        json={},
    )

    lost = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{lost_opp['public_id']}/lost",
        json={
            "reason": "Preço acima do orçamento",
        },
    )

    assert won.status_code == 200
    assert won.json()["status"] == "won"
    assert won.json()["won_at"] is not None

    assert lost.status_code == 200
    assert lost.json()["status"] == "lost"
    assert lost.json()["loss_reason"] == "Preço acima do orçamento"
    assert lost.json()["lost_at"] is not None

    metrics = client.get(
        f"/api/v1/workspaces/{workspace_id}/analytics/conversion"
    )

    assert metrics.status_code == 200

    payload = metrics.json()

    assert payload["total_opportunities"] == 2
    assert payload["won_opportunities"] == 1
    assert payload["lost_opportunities"] == 1
    assert payload["conversion_rate"] == 50.0


def test_closed_opportunity_cannot_move(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "opp-closed")
    workspace_id = str(workspace["public_id"])
    lead = _lead(
        client,
        workspace_id,
        "92911110006",
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
        },
    ).json()

    opportunity_id = str(created["public_id"])

    won = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity_id}/won",
        json={},
    )
    assert won.status_code == 200

    moved = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity_id}/move",
        json={
            "to_stage": "contatado",
        },
    )

    assert moved.status_code == 422


def test_opportunity_is_isolated_by_workspace(
    client: TestClient,
) -> None:
    first = _workspace(client, "opp-isolated-a")
    second = _workspace(client, "opp-isolated-b")

    first_id = str(first["public_id"])
    second_id = str(second["public_id"])

    lead = _lead(
        client,
        first_id,
        "92911110007",
    )

    created = client.post(
        f"/api/v1/workspaces/{first_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
        },
    ).json()

    response = client.get(
        f"/api/v1/workspaces/{second_id}/opportunities/"
        f"{created['public_id']}"
    )

    assert response.status_code == 404


def test_update_opportunity_value_and_owner(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "opp-update")
    workspace_id = str(workspace["public_id"])

    seller = _member(
        client,
        workspace_id,
        "seller-update@nexyra.demo",
    )
    lead = _lead(
        client,
        workspace_id,
        "92911110008",
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
            "value_amount": "500.00",
        },
    ).json()

    response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{created['public_id']}",
        json={
            "title": "Matrícula Radiologia",
            "value_amount": "1750.00",
            "owner_user_public_id": seller["public_id"],
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["title"] == "Matrícula Radiologia"
    assert payload["owner_user_public_id"] == seller["public_id"]
