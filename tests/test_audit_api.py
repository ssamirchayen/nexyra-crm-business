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
            "name": "Vendedor Auditoria",
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
            "name": "Lead Auditoria",
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
            "value_amount": "1500.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_workspace_creation_generates_audit_event(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-workspace")
    workspace_id = str(workspace["public_id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit"
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) >= 1
    assert payload[-1]["entity_type"] == "workspace"
    assert payload[-1]["action"] == "workspace.created"
    assert payload[-1]["before_data"] is None
    assert payload[-1]["after_data"]["slug"] == "audit-workspace"


def test_lead_update_records_before_and_after(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-lead")
    workspace_id = str(workspace["public_id"])
    lead = _lead(
        client,
        workspace_id,
        "92920000001",
    )

    lead_id = str(lead["public_id"])

    updated = client.patch(
        f"/api/v1/workspaces/{workspace_id}/leads/{lead_id}",
        json={
            "priority": "alta",
            "status": "contatado",
        },
    )

    assert updated.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit",
        params={
            "entity_type": "lead",
            "entity_public_id": lead_id,
            "action": "lead.updated",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    event = payload[0]

    assert event["before_data"]["priority"] == "media"
    assert event["before_data"]["status"] == "novo"
    assert event["after_data"]["priority"] == "alta"
    assert event["after_data"]["status"] == "contatado"


def test_opportunity_move_records_user_actor(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-actor")
    workspace_id = str(workspace["public_id"])

    seller = _member(
        client,
        workspace_id,
        "auditor@nexyra.demo",
    )
    lead = _lead(
        client,
        workspace_id,
        "92920000002",
    )
    opportunity = _opportunity(
        client,
        workspace_id,
        str(lead["public_id"]),
    )

    opportunity_id = str(opportunity["public_id"])
    seller_id = str(seller["public_id"])

    moved = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities/"
        f"{opportunity_id}/move",
        json={
            "to_stage": "contatado",
            "changed_by_user_public_id": seller_id,
            "note": "Contato realizado.",
        },
    )

    assert moved.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit",
        params={
            "entity_type": "opportunity",
            "entity_public_id": opportunity_id,
            "action": "opportunity.moved",
        },
    )

    assert response.status_code == 200

    event = response.json()[0]

    assert event["actor_type"] == "user"
    assert event["actor_user_public_id"] == seller_id
    assert event["before_data"]["stage"] == "novo"
    assert event["after_data"]["stage"] == "contatado"
    assert event["metadata"]["from_stage"] == "novo"
    assert event["metadata"]["to_stage"] == "contatado"


def test_activity_completion_is_audited(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-activity")
    workspace_id = str(workspace["public_id"])
    lead = _lead(
        client,
        workspace_id,
        "92920000003",
    )

    activity = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Retornar contato",
            "lead_public_id": lead["public_id"],
        },
    )

    assert activity.status_code == 201

    activity_id = str(activity.json()["public_id"])

    completed = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/"
        f"{activity_id}/complete"
    )

    assert completed.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit",
        params={
            "entity_type": "activity",
            "entity_public_id": activity_id,
            "action": "activity.completed",
        },
    )

    assert response.status_code == 200

    event = response.json()[0]

    assert event["before_data"]["status"] == "pending"
    assert event["after_data"]["status"] == "completed"
    assert event["after_data"]["completed_at"] is not None


def test_membership_changes_are_audited(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-member")
    workspace_id = str(workspace["public_id"])

    member = _member(
        client,
        workspace_id,
        "member-audit@nexyra.demo",
    )
    user_id = str(member["public_id"])

    updated = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{user_id}",
        json={
            "role": "manager",
        },
    )

    assert updated.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit",
        params={
            "entity_type": "membership",
            "entity_public_id": user_id,
            "action": "membership.updated",
        },
    )

    assert response.status_code == 200

    event = response.json()[0]

    assert event["before_data"]["role"] == "seller"
    assert event["after_data"]["role"] == "manager"


def test_audit_is_isolated_by_workspace(
    client: TestClient,
) -> None:
    first = _workspace(client, "audit-isolated-a")
    second = _workspace(client, "audit-isolated-b")

    first_id = str(first["public_id"])
    second_id = str(second["public_id"])

    lead = _lead(
        client,
        first_id,
        "92920000004",
    )
    lead_id = str(lead["public_id"])

    first_events = client.get(
        f"/api/v1/workspaces/{first_id}/audit",
        params={
            "entity_public_id": lead_id,
        },
    )
    second_events = client.get(
        f"/api/v1/workspaces/{second_id}/audit",
        params={
            "entity_public_id": lead_id,
        },
    )

    assert first_events.status_code == 200
    assert len(first_events.json()) >= 1

    assert second_events.status_code == 200
    assert second_events.json() == []


def test_audit_limit_is_validated(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "audit-limit")
    workspace_id = str(workspace["public_id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit",
        params={
            "limit": 501,
        },
    )

    assert response.status_code == 422
