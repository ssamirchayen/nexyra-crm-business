from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import PasswordResetRequest, User
from app.services.auth import AuthService

TEMP_PASSWORD = "Nexyra@Temp123"
NEW_PASSWORD = "Nexyra@Nova123"


@pytest.fixture
def client_and_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
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


def _bootstrap_user(client: TestClient) -> dict[str, object]:
    workspace = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Hardening Demo",
            "slug": "hardening-demo",
            "segment": "generic",
        },
    ).json()
    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Security Admin",
            "email": "security@nexyra.demo",
            "role": "admin",
            "initial_password": TEMP_PASSWORD,
        },
    )
    assert created.status_code == 201
    return workspace


def _login(client: TestClient, password: str = TEMP_PASSWORD) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "security@nexyra.demo", "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_account_is_temporarily_locked_after_repeated_failures(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    _bootstrap_user(client)

    for _ in range(4):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "security@nexyra.demo", "password": "Errada@123456"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "security@nexyra.demo", "password": "Errada@123456"},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

    correct_while_locked = client.post(
        "/api/v1/auth/login",
        json={"email": "security@nexyra.demo", "password": TEMP_PASSWORD},
    )
    assert correct_while_locked.status_code == 429


def test_session_inventory_and_revoke_others(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    _bootstrap_user(client)

    first = _login(client)
    second = _login(client)
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    sessions = client.get("/api/v1/auth/sessions", headers=first_headers)
    assert sessions.status_code == 200
    payload = sessions.json()
    assert len(payload) == 2
    assert sum(item["current"] for item in payload) == 1
    assert all(item["user_agent"] for item in payload)

    revoked = client.post(
        "/api/v1/auth/sessions/revoke-others",
        headers=first_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] == 1

    assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=second_headers).status_code == 401


def test_temporary_password_requires_change_before_commercial_api(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace = _bootstrap_user(client)
    login = _login(client)
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    blocked = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/dashboard/summary",
        headers=headers,
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Troca de senha obrigatória antes de acessar o CRM."

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": TEMP_PASSWORD,
            "new_password": NEW_PASSWORD,
        },
    )
    assert changed.status_code == 200

    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "security@nexyra.demo", "password": NEW_PASSWORD},
    )
    assert relogin.status_code == 200
    new_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}

    allowed = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/dashboard/summary",
        headers=new_headers,
    )
    assert allowed.status_code == 200


def test_password_recovery_foundation_stores_only_token_hash(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    _bootstrap_user(client)

    with testing_session() as db:
        prepared = AuthService(db).prepare_password_recovery(
            email="security@nexyra.demo"
        )
        assert prepared is not None
        user = db.scalar(select(User).where(User.email == "security@nexyra.demo"))
        assert user is not None
        stored = db.scalar(
            select(PasswordResetRequest).where(PasswordResetRequest.user_id == user.id)
        )
        assert stored is not None
        assert stored.token_hash != prepared.token
        assert prepared.token not in stored.token_hash
