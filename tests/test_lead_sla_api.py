from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Activity, Lead


@pytest.fixture
def client_and_session() -> Generator[
    tuple[TestClient, sessionmaker[Session]],
    None,
    None,
]:
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
        with TestClient(app) as client:
            yield client, testing_session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _workspace(client: TestClient, slug: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": f"Nexyra {slug}",
            "slug": slug,
            "segment": "education",
        },
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _member(
    client: TestClient,
    workspace_id: str,
    *,
    name: str,
    email: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"name": name, "email": email, "role": "seller"},
    )
    assert response.status_code == 201
    return response.json()


def _lead(
    client: TestClient,
    workspace_id: str,
    index: int,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": f"Lead SLA {index}",
        "phone": f"9298111{index:04d}",
        "interest": "Radiologia",
        "source": "site",
        "channel": "web",
        "priority": "media",
        "custom_fields": {"curso": "Radiologia"},
    }
    payload.update(overrides)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_created_at(
    testing_session: sessionmaker[Session],
    lead_public_id: str,
    value: datetime,
) -> None:
    with testing_session() as db:
        lead = db.scalar(select(Lead).where(Lead.public_id == lead_public_id))
        assert lead is not None
        lead.created_at = value
        db.commit()


def test_sla_defaults_and_new_lead_enters_queue(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client, "sla-defaults")
    lead = _lead(client, workspace_id, 1)

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/queue"
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["config"]["enabled"] is True
    assert payload["config"]["first_response_minutes"] == 15
    assert payload["metrics"]["total_attention"] == 1
    assert payload["items"][0]["lead_public_id"] == lead["public_id"]
    assert "awaiting_first_contact" in payload["items"][0]["reasons"]


def test_old_uncontacted_lead_breaches_first_response_sla(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace_id = _workspace(client, "sla-breach")
    lead = _lead(client, workspace_id, 1, priority="alta")
    _set_created_at(
        testing_session,
        str(lead["public_id"]),
        datetime.now(timezone.utc) - timedelta(hours=2),
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/queue"
    )
    assert response.status_code == 200
    payload = response.json()
    item = payload["items"][0]

    assert item["sla_state"] == "breached"
    assert "first_response_breached" in item["reasons"]
    assert payload["metrics"]["sla_breached"] == 1


def test_completed_contact_records_first_response_and_clears_clean_lead(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace_id = _workspace(client, "sla-contact")
    lead = _lead(client, workspace_id, 1)
    created_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    _set_created_at(testing_session, str(lead["public_id"]), created_at)

    activity = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "call",
            "title": "Primeiro contato",
            "lead_public_id": lead["public_id"],
        },
    )
    assert activity.status_code == 201
    completed = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/"
        f"{activity.json()['public_id']}/complete"
    )
    assert completed.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/queue"
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_overdue_followup_returns_contacted_lead_to_queue(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace_id = _workspace(client, "sla-followup")
    lead = _lead(client, workspace_id, 1)

    contact = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "whatsapp",
            "title": "Contato realizado",
            "lead_public_id": lead["public_id"],
        },
    ).json()
    assert client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/"
        f"{contact['public_id']}/complete"
    ).status_code == 200

    followup = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Retorno vencido",
            "lead_public_id": lead["public_id"],
            "due_at": "2020-01-01T12:00:00Z",
        },
    )
    assert followup.status_code == 201

    # Keep the completed contact recent so the queue reason is specifically the follow-up.
    with testing_session() as db:
        item = db.scalar(
            select(Activity).where(Activity.public_id == contact["public_id"])
        )
        assert item is not None
        item.completed_at = datetime.now(timezone.utc)
        db.commit()

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/queue"
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sla_state"] == "contacted"
    assert item["overdue_followups"] == 1
    assert "overdue_followup" in item["reasons"]


def test_queue_filters_by_owner_and_unassigned(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client, "sla-owner")
    seller = _member(
        client,
        workspace_id,
        name="Consultora Ana",
        email="ana-sla@nexyra.demo",
    )
    assigned = _lead(
        client,
        workspace_id,
        1,
        owner_user_public_id=seller["public_id"],
    )
    unassigned = _lead(client, workspace_id, 2)

    owner_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/queue"
        f"?owner_user_public_id={seller['public_id']}"
    )
    assert owner_response.status_code == 200
    assert [item["lead_public_id"] for item in owner_response.json()["items"]] == [
        assigned["public_id"]
    ]

    unassigned_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/queue?unassigned=true"
    )
    assert unassigned_response.status_code == 200
    assert [
        item["lead_public_id"] for item in unassigned_response.json()["items"]
    ] == [unassigned["public_id"]]


def test_sla_config_validates_warning_and_can_be_disabled(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client, "sla-config")
    _lead(client, workspace_id, 1)

    invalid = client.put(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/config",
        json={
            "enabled": True,
            "first_response_minutes": 10,
            "warning_before_minutes": 10,
            "follow_up_due_hours": 24,
            "stale_lead_hours": 24,
        },
    )
    assert invalid.status_code == 422

    saved = client.put(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/config",
        json={
            "enabled": False,
            "first_response_minutes": 30,
            "warning_before_minutes": 5,
            "follow_up_due_hours": 12,
            "stale_lead_hours": 48,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["enabled"] is False

    queue = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-sla/queue"
    )
    assert queue.status_code == 200
    assert queue.json()["items"] == []
