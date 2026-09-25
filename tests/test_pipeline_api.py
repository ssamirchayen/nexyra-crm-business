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
        json={
            "name": f"Empresa {slug}",
            "slug": slug,
            "segment": "education",
        },
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _member(client: TestClient, workspace_id: str, suffix: str) -> str:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": f"Vendedor {suffix}",
            "email": f"{suffix}@pipeline.demo",
            "role": "seller",
        },
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _lead(
    client: TestClient,
    workspace_id: str,
    *,
    name: str,
    phone: str,
    owner_user_public_id: str | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": name,
            "phone": phone,
            "interest": "Radiologia",
            "source": "instagram",
            "channel": "lead_ads",
            "custom_fields": {"curso": "Radiologia"},
            "owner_user_public_id": owner_user_public_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def _opportunity(
    client: TestClient,
    workspace_id: str,
    lead_public_id: str,
    *,
    value: str,
    stage: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "lead_public_id": lead_public_id,
        "value_amount": value,
    }
    if stage is not None:
        payload["stage"] = stage

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def test_pipeline_board_groups_open_opportunities(client: TestClient) -> None:
    workspace_id = _workspace(client, "pipeline-board")
    owner_id = _member(client, workspace_id, "board")

    lead_a = _lead(
        client,
        workspace_id,
        name="Mariana Lopes",
        phone="92911110001",
        owner_user_public_id=owner_id,
    )
    lead_b = _lead(
        client,
        workspace_id,
        name="Rafael Costa",
        phone="92911110002",
    )

    _opportunity(
        client,
        workspace_id,
        str(lead_a["public_id"]),
        value="1500.00",
    )
    _opportunity(
        client,
        workspace_id,
        str(lead_b["public_id"]),
        value="2500.00",
        stage="contatado",
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/pipeline/board"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["open_opportunities"] == 2
    assert payload["total_pipeline_value"] == "4000.00"
    assert payload["pipeline"][0] == "novo"

    stages = {item["code"]: item for item in payload["stages"]}
    assert stages["novo"]["total_count"] == 1
    assert stages["novo"]["total_value"] == "1500.00"
    assert stages["contatado"]["total_count"] == 1

    first_card = stages["novo"]["opportunities"][0]
    assert first_card["lead_name"] == "Mariana Lopes"
    assert first_card["owner_user_public_id"] == owner_id
    assert first_card["owner_name"] == "Vendedor board"


def test_pipeline_board_reflects_drag_move(client: TestClient) -> None:
    workspace_id = _workspace(client, "pipeline-move")
    lead = _lead(
        client,
        workspace_id,
        name="Lead Move",
        phone="92911110003",
    )
    opportunity = _opportunity(
        client,
        workspace_id,
        str(lead["public_id"]),
        value="900.00",
    )

    moved = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity['public_id']}/move",
        json={"to_stage": "interessado"},
    )
    assert moved.status_code == 200

    board = client.get(
        f"/api/v1/workspaces/{workspace_id}/pipeline/board"
    ).json()

    stages = {item["code"]: item for item in board["stages"]}
    assert stages["novo"]["total_count"] == 0
    assert stages["interessado"]["total_count"] == 1
    assert (
        stages["interessado"]["opportunities"][0]["public_id"]
        == opportunity["public_id"]
    )


def test_opportunity_search_filters_and_paginates(client: TestClient) -> None:
    workspace_id = _workspace(client, "opp-search")
    owner_id = _member(client, workspace_id, "search")

    lead_a = _lead(
        client,
        workspace_id,
        name="Mariana Pipeline",
        phone="92911110004",
        owner_user_public_id=owner_id,
    )
    lead_b = _lead(
        client,
        workspace_id,
        name="Outro Lead",
        phone="92911110005",
    )

    first = _opportunity(
        client,
        workspace_id,
        str(lead_a["public_id"]),
        value="1100.00",
    )
    second = _opportunity(
        client,
        workspace_id,
        str(lead_b["public_id"]),
        value="700.00",
    )

    won = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{second['public_id']}/won",
        json={},
    )
    assert won.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/opportunities/search",
        params={
            "q": "Mariana",
            "opportunity_status": "open",
            "owner_user_public_id": owner_id,
            "page": 1,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["total_pages"] == 1
    assert payload["items"][0]["public_id"] == first["public_id"]
    assert payload["items"][0]["lead_name"] == "Mariana Pipeline"


def test_pipeline_board_is_isolated_by_workspace(client: TestClient) -> None:
    first_id = _workspace(client, "pipeline-a")
    second_id = _workspace(client, "pipeline-b")

    lead = _lead(
        client,
        first_id,
        name="Lead apenas A",
        phone="92911110006",
    )
    _opportunity(
        client,
        first_id,
        str(lead["public_id"]),
        value="3200.00",
    )

    response = client.get(
        f"/api/v1/workspaces/{second_id}/pipeline/board"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["open_opportunities"] == 0
    assert payload["total_pipeline_value"] == "0.00"
