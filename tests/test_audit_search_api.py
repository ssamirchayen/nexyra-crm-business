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
            "name": "Marina Auditora",
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
            "name": "Lead Auditoria Busca",
            "phone": phone,
            "interest": "Radiologia",
            "custom_fields": {"curso": "Radiologia"},
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
            "value_amount": "1800.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_audit_search_returns_professional_page_and_facets(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-search-page")
    workspace_id = str(workspace["public_id"])
    lead = _lead(client, workspace_id, "92930000001")

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/search",
        params={"page": 1, "page_size": 10},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] >= 2
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["stats"]["total_events"] == payload["total"]
    assert payload["stats"]["system_events"] >= 2
    assert "workspace" in payload["available_entity_types"]
    assert "lead" in payload["available_entity_types"]
    assert "workspace.created" in payload["available_actions"]
    assert "lead.created" in payload["available_actions"]
    assert any(
        item["entity_public_id"] == lead["public_id"]
        for item in payload["items"]
    )


def test_audit_search_filters_user_actor_and_exposes_actor_name(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-search-actor")
    workspace_id = str(workspace["public_id"])
    member = _member(
        client,
        workspace_id,
        "marina.auditora@nexyra.demo",
    )
    lead = _lead(client, workspace_id, "92930000002")
    opportunity = _opportunity(
        client,
        workspace_id,
        str(lead["public_id"]),
    )

    moved = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity['public_id']}/move",
        json={
            "to_stage": "contatado",
            "changed_by_user_public_id": member["public_id"],
            "note": "Movimentação auditada.",
        },
    )
    assert moved.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/search",
        params={
            "actor_type": "user",
            "actor_user_public_id": member["public_id"],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert payload["stats"]["user_events"] == 1
    event = payload["items"][0]
    assert event["action"] == "opportunity.moved"
    assert event["actor_user_public_id"] == member["public_id"]
    assert event["actor_user_name"] == "Marina Auditora"
    assert event["actor_role"] == "seller"
    assert any(
        actor["public_id"] == member["public_id"]
        for actor in payload["available_actors"]
    )


def test_audit_search_supports_text_query_and_pagination(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-search-pagination")
    workspace_id = str(workspace["public_id"])
    lead = _lead(client, workspace_id, "92930000003")
    lead_id = str(lead["public_id"])

    for priority in ("alta", "urgente", "media"):
        response = client.patch(
            f"/api/v1/workspaces/{workspace_id}/leads/{lead_id}",
            json={"priority": priority},
        )
        assert response.status_code == 200

    search = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/search",
        params={"q": "lead.updated", "page": 1, "page_size": 2},
    )

    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 2
    assert payload["total_pages"] == 2
    assert all(item["action"] == "lead.updated" for item in payload["items"])

    second_page = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/search",
        params={"q": lead_id, "page": 2, "page_size": 2},
    )

    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["total"] >= 4
    assert second_payload["page"] == 2
    assert len(second_payload["items"]) >= 1


def test_audit_search_page_size_is_validated(client: TestClient) -> None:
    workspace = _workspace(client, "audit-search-limit")
    workspace_id = str(workspace["public_id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/search",
        params={"page_size": 101},
    )

    assert response.status_code == 422
