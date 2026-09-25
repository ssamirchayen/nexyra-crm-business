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


def _lead(
    client: TestClient,
    workspace_id: str,
    *,
    name: str,
    phone: str,
    source: str,
    priority: str = "media",
    campaign: str | None = None,
    owner_user_public_id: str | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={
            "name": name,
            "phone": phone,
            "source": source,
            "channel": "lead_ads" if source == "instagram" else "web",
            "campaign": campaign,
            "interest": "Radiologia",
            "priority": priority,
            "owner_user_public_id": owner_user_public_id,
            "custom_fields": {"curso": "Radiologia"},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_search_leads_supports_text_filters_and_pagination(
    client: TestClient,
) -> None:
    workspace_id = _workspace(client, "lead-search")

    _lead(
        client,
        workspace_id,
        name="Mariana Instagram",
        phone="92911110001",
        source="instagram",
        priority="alta",
        campaign="radiologia_setembro",
    )
    _lead(
        client,
        workspace_id,
        name="Rafael Google",
        phone="92911110002",
        source="google_ads",
        priority="media",
    )
    _lead(
        client,
        workspace_id,
        name="Bianca Instagram",
        phone="92911110003",
        source="instagram",
        priority="alta",
        campaign="radiologia_outubro",
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/search",
        params={
            "source": "instagram",
            "priority": "alta",
            "campaign": "radiologia",
            "page": 1,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total_pages"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "instagram"
    assert payload["items"][0]["created_at"]
    assert payload["items"][0]["updated_at"]


def test_search_leads_supports_owner_and_unassigned_filters(
    client: TestClient,
) -> None:
    workspace_id = _workspace(client, "lead-owner-search")

    member_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": "Vendedor Um",
            "email": "vendedor@lead.search",
            "role": "seller",
        },
    )
    assert member_response.status_code == 201
    member_id = str(member_response.json()["public_id"])

    _lead(
        client,
        workspace_id,
        name="Lead com dono",
        phone="92922220001",
        source="site",
        owner_user_public_id=member_id,
    )
    _lead(
        client,
        workspace_id,
        name="Lead sem dono",
        phone="92922220002",
        source="site",
    )

    owned = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/search",
        params={"owner_user_public_id": member_id},
    )
    unassigned = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/search",
        params={"unassigned": "true"},
    )

    assert owned.status_code == 200
    assert owned.json()["total"] == 1
    assert owned.json()["items"][0]["owner_user_public_id"] == member_id

    assert unassigned.status_code == 200
    assert unassigned.json()["total"] == 1
    assert unassigned.json()["items"][0]["owner_user_public_id"] is None


def test_search_leads_can_include_inactive_records(client: TestClient) -> None:
    workspace_id = _workspace(client, "lead-inactive-search")
    lead = _lead(
        client,
        workspace_id,
        name="Lead desativado",
        phone="92933330001",
        source="manual",
    )

    deactivate = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/"
        f"{lead['public_id']}/deactivate"
    )
    assert deactivate.status_code == 200

    active_only = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/search"
    )
    inactive = client.get(
        f"/api/v1/workspaces/{workspace_id}/leads/search",
        params={"active": "false"},
    )

    assert active_only.json()["total"] == 0
    assert inactive.json()["total"] == 1


def test_search_leads_is_isolated_by_workspace(client: TestClient) -> None:
    first_id = _workspace(client, "lead-search-a")
    second_id = _workspace(client, "lead-search-b")

    _lead(
        client,
        first_id,
        name="Lead apenas A",
        phone="92944440001",
        source="instagram",
    )

    response = client.get(
        f"/api/v1/workspaces/{second_id}/leads/search",
        params={"q": "Lead apenas A"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
