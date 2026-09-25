from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

PASSWORD = "Nexyra@12345"
NEW_PASSWORD = "Nexyra@67890"


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


def _create_login_user(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Nexyra Auth Demo",
            "slug": "nexyra-auth-demo",
            "segment": "generic",
        },
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    member_response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Admin Nexyra",
            "email": "admin@nexyra.demo",
            "role": "admin",
            "initial_password": PASSWORD,
        },
    )
    assert member_response.status_code == 201
    return workspace, member_response.json()


def _login(client: TestClient, password: str = PASSWORD) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nexyra.demo", "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_login_returns_session_and_workspace_access(client: TestClient) -> None:
    workspace, member = _create_login_user(client)

    payload = _login(client)

    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert payload["user"]["public_id"] == member["public_id"]
    assert payload["user"]["email"] == "admin@nexyra.demo"
    assert payload["workspaces"][0]["public_id"] == workspace["public_id"]
    assert payload["workspaces"][0]["role"] == "admin"
    assert "settings.update" in payload["workspaces"][0]["permissions"]


def test_me_requires_valid_bearer_session(client: TestClient) -> None:
    _create_login_user(client)
    token = _login(client)["access_token"]

    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@nexyra.demo"


def test_invalid_password_is_rejected(client: TestClient) -> None:
    _create_login_user(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nexyra.demo", "password": "SenhaErrada123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "E-mail ou senha inválidos."


def test_logout_revokes_session(client: TestClient) -> None:
    _create_login_user(client)
    token = _login(client)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200

    after = client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401


def test_change_password_revokes_old_session_and_accepts_new_password(
    client: TestClient,
) -> None:
    _create_login_user(client)
    token = _login(client)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
        },
    )
    assert changed.status_code == 200

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nexyra.demo", "password": PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nexyra.demo", "password": NEW_PASSWORD},
    )
    assert new_login.status_code == 200


def test_weak_initial_password_is_rejected(client: TestClient) -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Senha Fraca",
            "slug": "senha-fraca",
            "segment": "generic",
        },
    ).json()

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Usuário Teste",
            "email": "teste@nexyra.demo",
            "role": "seller",
            "initial_password": "fraca12345",
        },
    )

    assert response.status_code == 422
