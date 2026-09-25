from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

ADMIN_PASSWORD = "Nexyra@Admin123"
ADMIN_FINAL_PASSWORD = "Nexyra@Admin456"
SELLER_PASSWORD = "Nexyra@Seller123"
SELLER_FINAL_PASSWORD = "Nexyra@Seller456"


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


def _bootstrap_admin(client: TestClient) -> tuple[dict[str, object], dict[str, str]]:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Nexyra Secure",
            "slug": "nexyra-secure",
            "segment": "generic",
        },
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    member_response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Admin Secure",
            "email": "admin@secure.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert member_response.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@secure.demo", "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    temporary_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=temporary_headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": ADMIN_FINAL_PASSWORD,
        },
    )
    assert changed.status_code == 200
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@secure.demo", "password": ADMIN_FINAL_PASSWORD},
    )
    assert relogin.status_code == 200
    token = relogin.json()["access_token"]
    return workspace, {"Authorization": f"Bearer {token}"}


def _create_seller(
    client: TestClient,
    workspace_public_id: str,
    admin_headers: dict[str, str],
) -> tuple[dict[str, object], dict[str, str]]:
    member = client.post(
        f"/api/v1/workspaces/{workspace_public_id}/members",
        headers=admin_headers,
        json={
            "name": "Seller Secure",
            "email": "seller@secure.demo",
            "role": "seller",
            "initial_password": SELLER_PASSWORD,
        },
    )
    assert member.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "seller@secure.demo", "password": SELLER_PASSWORD},
    )
    assert login.status_code == 200
    temporary_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=temporary_headers,
        json={
            "current_password": SELLER_PASSWORD,
            "new_password": SELLER_FINAL_PASSWORD,
        },
    )
    assert changed.status_code == 200
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "seller@secure.demo", "password": SELLER_FINAL_PASSWORD},
    )
    assert relogin.status_code == 200
    token = relogin.json()["access_token"]
    return member.json(), {"Authorization": f"Bearer {token}"}


def test_protected_api_requires_auth_after_first_credential(client: TestClient) -> None:
    workspace, _ = _bootstrap_admin(client)

    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/leads"
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Autenticação necessária."


def test_valid_admin_can_access_workspace(client: TestClient) -> None:
    workspace, headers = _bootstrap_admin(client)

    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/dashboard/summary",
        headers=headers,
    )

    assert response.status_code == 200


def test_workspace_isolation_returns_403(client: TestClient) -> None:
    first_workspace, admin_headers = _bootstrap_admin(client)
    second_workspace = client.post(
        "/api/v1/workspaces",
        headers=admin_headers,
        json={
            "name": "Second Workspace",
            "slug": "second-workspace",
            "segment": "services",
        },
    ).json()
    _, seller_headers = _create_seller(
        client,
        first_workspace["public_id"],
        admin_headers,
    )

    response = client.get(
        f"/api/v1/workspaces/{second_workspace['public_id']}/leads",
        headers=seller_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Você não possui acesso ativo a esta empresa."


def test_seller_cannot_read_management_analytics(client: TestClient) -> None:
    workspace, admin_headers = _bootstrap_admin(client)
    _, seller_headers = _create_seller(
        client,
        workspace["public_id"],
        admin_headers,
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/reports/analytics",
        headers=seller_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissão necessária: analytics.read."


def test_seller_cannot_create_team_member(client: TestClient) -> None:
    workspace, admin_headers = _bootstrap_admin(client)
    _, seller_headers = _create_seller(
        client,
        workspace["public_id"],
        admin_headers,
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        headers=seller_headers,
        json={
            "name": "Blocked User",
            "email": "blocked@secure.demo",
            "role": "seller",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissão necessária: members.create."


def test_seller_can_assign_lead_to_self_but_not_another_user(client: TestClient) -> None:
    workspace, admin_headers = _bootstrap_admin(client)
    seller, seller_headers = _create_seller(
        client,
        workspace["public_id"],
        admin_headers,
    )

    own_lead = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=seller_headers,
        json={
            "name": "Lead Próprio",
            "source": "manual",
            "channel": "crm",
            "owner_user_public_id": seller["public_id"],
        },
    )
    assert own_lead.status_code == 201

    admin_context = client.get("/api/v1/auth/me", headers=admin_headers).json()
    admin_public_id = admin_context["user"]["public_id"]
    blocked = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=seller_headers,
        json={
            "name": "Lead Bloqueado",
            "source": "manual",
            "channel": "crm",
            "owner_user_public_id": admin_public_id,
        },
    )

    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Permissão necessária: leads.assign."


def test_authenticated_mutation_is_audited_as_real_user(client: TestClient) -> None:
    workspace, headers = _bootstrap_admin(client)
    me = client.get("/api/v1/auth/me", headers=headers).json()

    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=headers,
        json={
            "name": "Lead Auditável",
            "source": "manual",
            "channel": "crm",
        },
    )
    assert created.status_code == 201

    audit = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/audit/search",
        headers=headers,
        params={"action": "lead.created"},
    )
    assert audit.status_code == 200
    event = audit.json()["items"][0]
    assert event["actor_type"] == "user"
    assert event["actor_user_public_id"] == me["user"]["public_id"]
    assert event["actor_user_name"] == "Admin Secure"


def test_authenticated_workspace_creator_becomes_admin(client: TestClient) -> None:
    _, headers = _bootstrap_admin(client)

    created = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={
            "name": "Novo Workspace Seguro",
            "slug": "novo-workspace-seguro",
            "segment": "retail",
        },
    )
    assert created.status_code == 201

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    access = next(
        item
        for item in me.json()["workspaces"]
        if item["public_id"] == created.json()["public_id"]
    )
    assert access["role"] == "admin"
    assert "workspace.update" in access["permissions"]
