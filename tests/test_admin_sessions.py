from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import (
    AuditEvent,
    AuthSession,
    User,
    Workspace,
    WorkspaceMembership,
)

TEMP_PASSWORD = "Nexyra@Temp123"
NEW_PASSWORD = "Nexyra@Nova123"


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
        with TestClient(app) as test_client:
            yield test_client, testing_session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def setup_accounts(client, factory):
    workspace = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Session test",
            "slug": "session-test",
            "segment": "generic",
        },
    ).json()["public_id"]
    # Create memberships before provisioning credentials disables bootstrap.
    users = {}
    for role in ("admin", "manager", "seller", "operator"):
        response = client.post(
            f"/api/v1/workspaces/{workspace}/members",
            json={
                "name": role,
                "email": f"{role}@example.test",
                "role": role,
            },
        )
        assert response.status_code == 201, response.text
        users[role] = response.json()["public_id"]
    from app.services.auth import AuthService

    with factory() as db:
        for user in db.scalars(select(User)):
            AuthService(db).configure_password(user=user, password=TEMP_PASSWORD)
        db.commit()

    def login(role):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"{role}@example.test",
                "password": TEMP_PASSWORD,
            },
        )
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    headers = {role: login(role) for role in users}
    return workspace, users, headers, login


def test_admin_revokes_one_session_and_audits(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, login = setup_accounts(client, factory)
    second = login("seller")
    path = f"/api/v1/workspaces/{workspace}/members/{users['seller']}/sessions"
    response = client.get(path, headers=headers["admin"])
    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert "token" not in response.text and "password" not in response.text
    target = client.get("/api/v1/auth/sessions", headers=headers["seller"]).json()
    target_id = next(item["public_id"] for item in target if item["current"])
    revoke = path + f"/{target_id}/revoke"
    assert client.post(revoke, headers=headers["admin"]).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers["seller"]).status_code == 401
    assert client.get("/api/v1/auth/me", headers=second).status_code == 200
    assert len(client.get(path, headers=headers["admin"]).json()) == 1
    assert client.post(revoke, headers=headers["admin"]).status_code == 200
    with factory() as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "session.revoked_by_admin")
        ).all()
        assert len(events) == 1
        assert events[0].actor_membership_id is not None
        assert events[0].metadata_json == {"user_public_id": users["seller"]}


@pytest.mark.parametrize("role", ["manager", "seller", "operator"])
def test_non_admin_cannot_manage_sessions(client_and_session, role):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    path = f"/api/v1/workspaces/{workspace}/members/{users['seller']}/sessions"
    assert client.get(path, headers=headers[role]).status_code == 403
    assert (
        client.post(path + "/unknown/revoke", headers=headers[role]).status_code == 403
    )


def test_session_scope_and_current_session(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    root = f"/api/v1/workspaces/{workspace}/members"
    own = client.get(
        f"{root}/{users['admin']}/sessions", headers=headers["admin"]
    ).json()[0]
    assert own["current"] is True
    assert (
        client.post(
            f"{root}/{users['admin']}/sessions/{own['public_id']}/revoke",
            headers=headers["admin"],
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{root}/{users['seller']}/sessions/{own['public_id']}/revoke",
            headers=headers["admin"],
        ).status_code
        == 404
    )
    assert (
        client.get(f"{root}/USR-absent/sessions", headers=headers["admin"]).status_code
        == 404
    )
    with factory() as db:
        other = Workspace(name="Other", slug="other", segment="generic")
        db.add(other)
        db.flush()
        user = db.scalar(select(User).where(User.public_id == users["seller"]))
        db.add(
            WorkspaceMembership(
                workspace_id=other.id, user_id=user.id, role="seller", active=False
            )
        )
        db.commit()
        other_public_id = other.public_id
    shared = f"{root}/{users['seller']}/sessions"
    assert client.get(shared, headers=headers["admin"]).status_code == 409
    assert (
        client.post(shared + "/unknown/revoke", headers=headers["admin"]).status_code
        == 409
    )
    assert (
        client.get(
            f"/api/v1/workspaces/{other_public_id}/members/{users['seller']}/sessions",
            headers=headers["admin"],
        ).status_code
        == 403
    )


def test_expired_sessions_hidden_and_anonymous_denied(client_and_session):
    client, factory = client_and_session
    workspace, users, headers, _ = setup_accounts(client, factory)
    path = f"/api/v1/workspaces/{workspace}/members/{users['seller']}/sessions"
    with factory() as db:
        user = db.scalar(select(User).where(User.public_id == users["seller"]))
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        session.expires_at = datetime.now(UTC) - timedelta(seconds=10)
        db.commit()
    assert client.get(path, headers=headers["admin"]).json() == []
    assert client.get(path).status_code == 401


def test_bootstrap_does_not_expose_sessions(client_and_session):
    client, _ = client_and_session
    path = "/api/v1/workspaces/unknown/members/unknown/sessions"
    assert client.get(path).status_code == 401
    assert client.post(path + "/unknown/revoke").status_code == 401
