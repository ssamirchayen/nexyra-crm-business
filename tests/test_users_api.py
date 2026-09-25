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
            "segment": "generic",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_roles_are_available(client: TestClient) -> None:
    response = client.get("/api/v1/roles")
    assert response.status_code == 200
    roles = {item["role"] for item in response.json()}
    assert roles == {"admin", "manager", "seller", "operator"}


def test_create_seller_in_workspace(client: TestClient) -> None:
    workspace = _workspace(client, "loja-a")
    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Mariana Lopes",
            "email": "mariana@nexyra.demo",
            "role": "seller",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["public_id"].startswith("USR-")
    assert payload["role"] == "seller"
    assert payload["membership_active"] is True


def test_same_user_can_belong_to_two_workspaces(
    client: TestClient,
) -> None:
    first = _workspace(client, "empresa-a")
    second = _workspace(client, "empresa-b")

    first_response = client.post(
        f"/api/v1/workspaces/{first['public_id']}/members",
        json={
            "name": "Rafael Costa",
            "email": "rafael@nexyra.demo",
            "role": "seller",
        },
    )
    second_response = client.post(
        f"/api/v1/workspaces/{second['public_id']}/members",
        json={
            "name": "Rafael Costa",
            "email": "rafael@nexyra.demo",
            "role": "manager",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["public_id"] == second_response.json()["public_id"]
    assert first_response.json()["role"] == "seller"
    assert second_response.json()["role"] == "manager"


def test_members_are_isolated_by_workspace(
    client: TestClient,
) -> None:
    first = _workspace(client, "isolada-a")
    second = _workspace(client, "isolada-b")

    created = client.post(
        f"/api/v1/workspaces/{first['public_id']}/members",
        json={
            "name": "Ana Beatriz",
            "email": "ana@nexyra.demo",
            "role": "seller",
        },
    ).json()

    response = client.get(
        f"/api/v1/workspaces/{second['public_id']}/members/"
        f"{created['public_id']}"
    )
    assert response.status_code == 404


def test_change_role_and_read_permissions(
    client: TestClient,
) -> None:
    workspace = _workspace(client, "permissoes")

    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Bianca Souza",
            "email": "bianca@nexyra.demo",
            "role": "seller",
        },
    ).json()

    workspace_id = workspace["public_id"]
    user_id = created["public_id"]

    updated = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{user_id}",
        json={"role": "manager"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "manager"

    permissions = client.get(
        f"/api/v1/workspaces/{workspace_id}/members/"
        f"{user_id}/permissions"
    )
    assert permissions.status_code == 200
    payload = permissions.json()
    assert "leads.assign" in payload["permissions"]
    assert "analytics.read" in payload["permissions"]


def test_deactivate_membership(client: TestClient) -> None:
    workspace = _workspace(client, "desativacao")

    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Carlos Lima",
            "email": "carlos@nexyra.demo",
            "role": "operator",
        },
    ).json()

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members/"
        f"{created['public_id']}/deactivate"
    )
    assert response.status_code == 200
    assert response.json()["membership_active"] is False


def test_invalid_role_returns_422(client: TestClient) -> None:
    workspace = _workspace(client, "papel-invalido")

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Usuário Teste",
            "email": "teste@nexyra.demo",
            "role": "superuser",
        },
    )
    assert response.status_code == 422
