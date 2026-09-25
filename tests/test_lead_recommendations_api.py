from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Activity, IntegrationSource, Lead, Opportunity, WhatsAppMessage


@pytest.fixture
def client_and_session() -> Generator[
    tuple[TestClient, sessionmaker[Session]], None, None
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
        json={"name": f"Nexyra {slug}", "slug": slug, "segment": "education"},
    )
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _member(client: TestClient, workspace_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "name": "Ana Comercial",
            "email": "ana-rec@nexyra.demo",
            "role": "seller",
        },
    )
    assert response.status_code == 201
    return response.json()


def _lead(client: TestClient, workspace_id: str, index: int, **overrides: object):
    payload: dict[str, object] = {
        "name": f"Lead Recomendação {index}",
        "phone": f"9298777{index:04d}",
        "interest": "Radiologia",
        "source": "site",
        "channel": "web",
        "priority": "media",
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/workspaces/{workspace_id}/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_unassigned_lead_recommends_assignment(client_and_session) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client, "rec-unassigned")
    lead = _lead(client, workspace_id, 1)

    response = client.get(f"/api/v1/workspaces/{workspace_id}/lead-recommendations")
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["lead_public_id"] == lead["public_id"]
    assert item["action"] == "assign_owner"
    assert "unassigned" in item["reason_codes"]
    assert response.json()["metrics"]["unassigned"] == 1


def test_assigned_old_lead_recommends_first_contact(client_and_session) -> None:
    client, sessions = client_and_session
    workspace_id = _workspace(client, "rec-sla")
    member = _member(client, workspace_id)
    lead = _lead(
        client,
        workspace_id,
        1,
        owner_user_public_id=member["public_id"],
        priority="alta",
    )
    with sessions() as db:
        model = db.scalar(select(Lead).where(Lead.public_id == lead["public_id"]))
        assert model is not None
        model.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()

    response = client.get(f"/api/v1/workspaces/{workspace_id}/lead-recommendations")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["action"] == "first_contact"
    assert "first_response_breached" in item["reason_codes"]
    assert item["urgency"] in {"high", "critical"}


def test_latest_inbound_whatsapp_recommends_reply(client_and_session) -> None:
    client, sessions = client_and_session
    workspace_id = _workspace(client, "rec-whatsapp")
    member = _member(client, workspace_id)
    lead = _lead(client, workspace_id, 1, owner_user_public_id=member["public_id"])

    with sessions() as db:
        lead_model = db.scalar(select(Lead).where(Lead.public_id == lead["public_id"]))
        workspace_model = lead_model.workspace_id if lead_model else None
        assert lead_model is not None and workspace_model is not None
        source = IntegrationSource(
            workspace_id=workspace_model,
            provider="whatsapp_cloud",
            name="WhatsApp teste",
            source="whatsapp",
            channel="whatsapp",
            routing_config={},
            provider_config={},
            active=True,
        )
        db.add(source)
        db.flush()
        db.add(
            WhatsAppMessage(
                workspace_id=workspace_model,
                integration_source_id=source.id,
                lead_id=lead_model.id,
                provider_message_id="wamid.rec.1",
                direction="inbound",
                message_type="text",
                from_phone=lead_model.normalized_phone,
                to_phone="5592000000000",
                body="Tenho interesse",
                status="received",
                metadata_json={},
            )
        )
        # Mark a recent contact so SLA doesn't dominate this test.
        db.add(
            Activity(
                workspace_id=workspace_model,
                lead_id=lead_model.id,
                activity_type="whatsapp",
                title="Contato recente",
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    response = client.get(f"/api/v1/workspaces/{workspace_id}/lead-recommendations")
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["action"] == "reply_whatsapp"
    assert item["awaiting_whatsapp_reply"] is True
    assert item["suggested_channel"] == "whatsapp"


def test_overdue_followup_is_prioritized(client_and_session) -> None:
    client, sessions = client_and_session
    workspace_id = _workspace(client, "rec-followup")
    member = _member(client, workspace_id)
    lead = _lead(client, workspace_id, 1, owner_user_public_id=member["public_id"])
    contact = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "call",
            "title": "Contato",
            "lead_public_id": lead["public_id"],
        },
    ).json()
    assert client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/{contact['public_id']}/complete"
    ).status_code == 200
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "follow_up",
            "title": "Retorno",
            "lead_public_id": lead["public_id"],
            "due_at": "2020-01-01T10:00:00Z",
        },
    )
    assert response.status_code == 201
    with sessions() as db:
        activity = db.scalar(
            select(Activity).where(Activity.public_id == contact["public_id"])
        )
        assert activity is not None
        activity.completed_at = datetime.now(timezone.utc)
        db.commit()

    board = client.get(f"/api/v1/workspaces/{workspace_id}/lead-recommendations")
    assert board.status_code == 200
    item = board.json()["items"][0]
    assert item["action"] == "follow_up"
    assert "overdue_followup" in item["reason_codes"]


def test_stale_open_opportunity_recommends_recovery(client_and_session) -> None:
    client, sessions = client_and_session
    workspace_id = _workspace(client, "rec-opportunity")
    member = _member(client, workspace_id)
    lead = _lead(client, workspace_id, 1, owner_user_public_id=member["public_id"])
    contact = client.post(
        f"/api/v1/workspaces/{workspace_id}/activities",
        json={
            "activity_type": "call",
            "title": "Contato",
            "lead_public_id": lead["public_id"],
        },
    ).json()
    assert client.post(
        f"/api/v1/workspaces/{workspace_id}/activities/{contact['public_id']}/complete"
    ).status_code == 200

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/opportunities",
        json={
            "lead_public_id": lead["public_id"],
            "title": "Matrícula Radiologia",
            "value_amount": 1500,
            "stage": "proposta",
        },
    )
    assert created.status_code == 201, created.text
    with sessions() as db:
        opportunity = db.scalar(
            select(Opportunity).where(
                Opportunity.public_id == created.json()["public_id"]
            )
        )
        assert opportunity is not None
        opportunity.updated_at = datetime.now(timezone.utc) - timedelta(days=5)
        db.commit()

    response = client.get(f"/api/v1/workspaces/{workspace_id}/lead-recommendations")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["action"] == "recover_opportunity"
    assert item["opportunity_at_risk"] is True
    assert response.json()["metrics"]["opportunities_at_risk"] == 1


def test_recommendation_filters_by_action(client_and_session) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client, "rec-filter")
    _lead(client, workspace_id, 1)

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-recommendations?action=assign_owner"
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    empty = client.get(
        f"/api/v1/workspaces/{workspace_id}/lead-recommendations?action=follow_up"
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []
