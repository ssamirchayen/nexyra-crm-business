from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Activity, LeadCadenceEnrollment


@pytest.fixture
def client_and_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)
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


def _workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces", json={"name": "Nexyra Cadence", "slug": "cadence-tests", "segment": "education"})
    assert response.status_code == 201
    return str(response.json()["public_id"])


def _lead(client: TestClient, workspace_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={"name": "Maria Cadência", "phone": "92981112222", "interest": "Radiologia", "source": "site", "channel": "web"},
    )
    assert response.status_code == 201
    return response.json()


def _cadence(client: TestClient, workspace_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-cadences",
        json={
            "name": "Lead novo 2 passos",
            "description": "Sequência de teste",
            "stop_on_reply": True,
            "steps": [
                {"delay_minutes": 0, "action_type": "whatsapp", "title": "WhatsApp para {{lead_name}}", "message_template": "Olá {{lead_name}}, interesse: {{interest}}"},
                {"delay_minutes": 60, "action_type": "follow_up", "title": "Retorno", "message_template": None},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_list_and_preview_cadence(client_and_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client)
    cadence = _cadence(client, workspace_id)
    assert cadence["steps"][0]["position"] == 1
    listed = client.get(f"/api/v1/workspaces/{workspace_id}/lead-cadences")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Lead novo 2 passos"
    preview = client.get(f"/api/v1/workspaces/{workspace_id}/lead-cadences/{cadence['public_id']}/preview")
    assert preview.status_code == 200
    assert len(preview.json()["items"]) == 2


def test_enroll_and_process_due_creates_activity(client_and_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, testing_session = client_and_session
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)
    cadence = _cadence(client, workspace_id)
    enrolled = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-cadence-enrollments",
        json={"lead_public_id": lead["public_id"], "cadence_public_id": cadence["public_id"]},
    )
    assert enrolled.status_code == 201, enrolled.text
    result = client.post(f"/api/v1/workspaces/{workspace_id}/lead-cadences/process-due")
    assert result.status_code == 200, result.text
    assert result.json()["activities_created"] == 1
    with testing_session() as db:
        activity = db.scalar(select(Activity).where(Activity.title.like("WhatsApp%")))
        assert activity is not None
        assert activity.activity_type == "whatsapp"
        assert activity.description == "Olá Maria Cadência, interesse: Radiologia"


def test_duplicate_active_enrollment_is_rejected(client_and_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)
    cadence = _cadence(client, workspace_id)
    payload = {"lead_public_id": lead["public_id"], "cadence_public_id": cadence["public_id"]}
    assert client.post(f"/api/v1/workspaces/{workspace_id}/lead-cadence-enrollments", json=payload).status_code == 201
    duplicated = client.post(f"/api/v1/workspaces/{workspace_id}/lead-cadence-enrollments", json=payload)
    assert duplicated.status_code == 422


def test_cancel_enrollment(client_and_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = client_and_session
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)
    cadence = _cadence(client, workspace_id)
    enrolled = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-cadence-enrollments",
        json={"lead_public_id": lead["public_id"], "cadence_public_id": cadence["public_id"]},
    ).json()
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-cadence-enrollments/{enrolled['public_id']}/cancel"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_process_future_step_only_when_due(client_and_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, testing_session = client_and_session
    workspace_id = _workspace(client)
    lead = _lead(client, workspace_id)
    cadence = _cadence(client, workspace_id)
    client.post(
        f"/api/v1/workspaces/{workspace_id}/lead-cadence-enrollments",
        json={"lead_public_id": lead["public_id"], "cadence_public_id": cadence["public_id"]},
    )
    first = client.post(f"/api/v1/workspaces/{workspace_id}/lead-cadences/process-due").json()
    assert first["activities_created"] == 1
    second = client.post(f"/api/v1/workspaces/{workspace_id}/lead-cadences/process-due").json()
    assert second["activities_created"] == 0
    with testing_session() as db:
        enrollment = db.scalar(select(LeadCadenceEnrollment))
        assert enrollment is not None
        enrollment.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    third = client.post(f"/api/v1/workspaces/{workspace_id}/lead-cadences/process-due").json()
    assert third["activities_created"] == 1
    assert third["completed"] == 1
