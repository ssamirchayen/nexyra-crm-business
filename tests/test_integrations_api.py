from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AuditEvent, IntegrationSource

ADMIN_PASSWORD = "Nexyra@Integracao123"
ADMIN_FINAL_PASSWORD = "Nexyra@Integracao456"
SELLER_PASSWORD = "Nexyra@Seller123"
SELLER_FINAL_PASSWORD = "Nexyra@Seller456"


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


def _bootstrap_admin(client: TestClient) -> tuple[dict[str, object], dict[str, str]]:
    workspace = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Nexyra Integrations",
            "slug": "nexyra-integrations",
            "segment": "generic",
        },
    ).json()
    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Integration Admin",
            "email": "integration-admin@nexyra.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert created.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "integration-admin@nexyra.demo",
            "password": ADMIN_PASSWORD,
        },
    )
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
        json={
            "email": "integration-admin@nexyra.demo",
            "password": ADMIN_FINAL_PASSWORD,
        },
    )
    assert relogin.status_code == 200
    return workspace, {
        "Authorization": f"Bearer {relogin.json()['access_token']}"
    }


def _create_source(
    client: TestClient,
    workspace_public_id: str,
    headers: dict[str, str],
    *,
    name: str = "Landing Page Setembro",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_public_id}/integrations",
        headers=headers,
        json={
            "provider": "website",
            "name": name,
            "source": "website",
            "channel": "form",
            "default_campaign": "Setembro",
            "routing_config": {},
            "provider_config": {},
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_overview_exposes_catalog_and_workspace_intake_endpoint(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)

    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/overview",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_sources"] == 0
    assert payload["intake_endpoint"].endswith(
        f"/{workspace['public_id']}/leads/intake"
    )
    provider_codes = {item["code"] for item in payload["providers"]}
    assert {"api_intake", "website", "webhook", "meta", "whatsapp"} <= provider_codes


def test_admin_can_create_source_and_action_is_audited(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    created = _create_source(client, workspace["public_id"], headers)

    assert created["provider"] == "website"
    assert created["source"] == "website"
    assert created["channel"] == "form"
    assert created["active"] is True

    with testing_session() as db:
        stored = db.scalar(
            select(IntegrationSource).where(
                IntegrationSource.public_id == created["public_id"]
            )
        )
        assert stored is not None
        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_public_id == created["public_id"],
                AuditEvent.action == "integration_source.created",
            )
        )
        assert audit is not None
        assert audit.actor_type == "user"


def test_duplicate_source_name_returns_conflict(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    _create_source(client, workspace["public_id"], headers)

    duplicated = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations",
        headers=headers,
        json={
            "provider": "webhook",
            "name": "Landing Page Setembro",
            "source": "webhook",
            "channel": "webhook",
        },
    )

    assert duplicated.status_code == 409


def test_invalid_provider_returns_validation_error(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations",
        headers=headers,
        json={
            "provider": "provedor_inexistente",
            "name": "Fonte inválida",
            "source": "teste",
            "channel": "teste",
        },
    )

    assert response.status_code == 422


def test_source_can_be_deactivated_and_reactivated(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    created = _create_source(client, workspace["public_id"], headers)
    source_id = created["public_id"]

    disabled = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/{source_id}/deactivate",
        headers=headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False

    enabled = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/{source_id}/activate",
        headers=headers,
    )
    assert enabled.status_code == 200
    assert enabled.json()["active"] is True


def test_seller_cannot_read_or_change_integration_settings(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, admin_headers = _bootstrap_admin(client)
    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        headers=admin_headers,
        json={
            "name": "Integration Seller",
            "email": "integration-seller@nexyra.demo",
            "role": "seller",
            "initial_password": SELLER_PASSWORD,
        },
    )
    assert created.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "integration-seller@nexyra.demo",
            "password": SELLER_PASSWORD,
        },
    )
    temporary = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=temporary,
        json={
            "current_password": SELLER_PASSWORD,
            "new_password": SELLER_FINAL_PASSWORD,
        },
    )
    assert changed.status_code == 200
    relogin = client.post(
        "/api/v1/auth/login",
        json={
            "email": "integration-seller@nexyra.demo",
            "password": SELLER_FINAL_PASSWORD,
        },
    )
    seller_headers = {
        "Authorization": f"Bearer {relogin.json()['access_token']}"
    }

    overview = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations/overview",
        headers=seller_headers,
    )
    assert overview.status_code == 403
    assert overview.json()["detail"] == "Permissão necessária: settings.read."


def test_configured_source_intake_applies_source_channel_and_default_campaign(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    created = _create_source(client, workspace["public_id"], headers)

    response = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{created['public_id']}/intake"
        ),
        headers=headers,
        json={
            "name": "Lead Integração",
            "email": "lead.integracao@nexyra.demo",
            "source": "manual_override",
            "channel": "manual_override",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "created"
    assert payload["lead"]["source"] == "website"
    assert payload["lead"]["channel"] == "form"
    assert payload["lead"]["campaign"] == "Setembro"


def test_inactive_source_blocks_intake(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    created = _create_source(client, workspace["public_id"], headers)
    client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{created['public_id']}/deactivate"
        ),
        headers=headers,
    )

    response = client.post(
        (
            f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
            f"{created['public_id']}/intake"
        ),
        headers=headers,
        json={"name": "Lead Bloqueado"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Esta fonte de integração está desativada."


def test_provider_config_rejects_plaintext_secrets(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations",
        headers=headers,
        json={
            "provider": "custom_api",
            "name": "API insegura",
            "source": "api",
            "channel": "custom",
            "provider_config": {"access_token": "nao-deve-ser-salvo"},
        },
    )

    assert response.status_code == 422
