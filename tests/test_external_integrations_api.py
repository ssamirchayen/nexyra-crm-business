from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import AuditEvent, IntegrationSource

ADMIN_PASSWORD = "Nexyra@Integracao123"
ADMIN_FINAL_PASSWORD = "Nexyra@Integracao456"


def _client_fixture() -> Generator[
    tuple[TestClient, sessionmaker[Session]],
    None,
    None,
]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(
        bind=engine,
        autoflush=False,
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


def _bootstrap_admin(client: TestClient) -> tuple[dict[str, object], dict[str, str]]:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Nexyra External Intake",
            "slug": "nexyra-external-intake",
            "segment": "generic",
        },
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "External Admin",
            "email": "external-admin@nexyra.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert created.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "external-admin@nexyra.demo",
            "password": ADMIN_PASSWORD,
        },
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
        json={
            "email": "external-admin@nexyra.demo",
            "password": ADMIN_FINAL_PASSWORD,
        },
    )
    assert relogin.status_code == 200
    return workspace, {
        "Authorization": f"Bearer {relogin.json()['access_token']}"
    }


def _create_source(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
    *,
    provider: str = "webhook",
    provider_config: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations",
        headers=headers,
        json={
            "provider": provider,
            "name": f"Fonte {provider}",
            "source": "website" if provider == "website" else "webhook",
            "channel": "form" if provider == "website" else "webhook",
            "default_campaign": "Campanha Externa",
            "provider_config": provider_config or {},
        },
    )
    assert response.status_code == 201
    return response.json()


def _rotate_key(
    client: TestClient,
    workspace_id: str,
    source_id: str,
    headers: dict[str, str],
) -> dict[str, object]:
    response = client.post(
        (
            f"/api/v1/workspaces/{workspace_id}/integrations/"
            f"{source_id}/external-key/rotate"
        ),
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def test_external_key_is_returned_once_and_only_hash_is_persisted() -> None:
    for client, testing_session in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(client, workspace["public_id"], headers)
        credential = _rotate_key(
            client,
            workspace["public_id"],
            source["public_id"],
            headers,
        )

        assert credential["intake_key"].startswith("nxy_int_")
        assert credential["header_name"] == "X-Nexyra-Intake-Key"
        assert credential["intake_endpoint"].endswith(
            f"/{source['public_id']}/intake"
        )

        with testing_session() as db:
            stored = db.scalar(
                select(IntegrationSource).where(
                    IntegrationSource.public_id == source["public_id"]
                )
            )
            assert stored is not None
            assert stored.intake_key_hash
            assert credential["intake_key"] not in stored.intake_key_hash
            assert stored.intake_key_prefix == credential["key_prefix"]


def test_external_intake_rejects_invalid_key() -> None:
    for client, _ in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(client, workspace["public_id"], headers)
        _rotate_key(client, workspace["public_id"], source["public_id"], headers)

        response = client.post(
            f"/api/v1/external/integrations/{source['public_id']}/intake",
            headers={"X-Nexyra-Intake-Key": "nxy_int_invalida"},
            json={"name": "Lead Inválido"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Credencial de integração inválida."


def test_external_intake_normalizes_aliases_and_forces_source_defaults() -> None:
    for client, testing_session in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(client, workspace["public_id"], headers)
        credential = _rotate_key(
            client, workspace["public_id"], source["public_id"], headers
        )

        response = client.post(
            f"/api/v1/external/integrations/{source['public_id']}/intake",
            headers={
                "X-Nexyra-Intake-Key": credential["intake_key"],
                "X-Idempotency-Key": "form-123",
                "X-Request-ID": "req-external-123",
            },
            json={
                "nome": "Maria da Silva",
                "telefone": "(92) 99999-9999",
                "email": "MARIA@EXAMPLE.COM",
                "interesse": "Plano Empresarial",
                "source": "nao-pode-sobrescrever",
                "channel": "nao-pode-sobrescrever",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["action"] == "created"
        assert payload["source"] == "webhook"
        assert payload["channel"] == "webhook"
        assert payload["campaign"] == "Campanha Externa"
        assert payload["intake_count"] == 1

        repeated = client.post(
            f"/api/v1/external/integrations/{source['public_id']}/intake",
            headers={
                "X-Nexyra-Intake-Key": credential["intake_key"],
                "X-Idempotency-Key": "form-123",
            },
            json={"nome": "Maria da Silva Atualizada"},
        )
        assert repeated.status_code == 200
        repeated_payload = repeated.json()
        assert repeated_payload["action"] == "duplicate_updated"
        assert repeated_payload["lead_public_id"] == payload["lead_public_id"]
        assert repeated_payload["intake_count"] == 2

        with testing_session() as db:
            event = db.scalar(
                select(AuditEvent)
                .where(
                    AuditEvent.entity_public_id == source["public_id"],
                    AuditEvent.action
                    == "integration_source.external_intake_received",
                )
                .order_by(AuditEvent.id.asc())
            )
            assert event is not None
            assert event.actor_type == "integration"
            assert event.metadata_json["request_id"] == "req-external-123"


def test_field_mapping_accepts_nested_payload() -> None:
    for client, _ in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(
            client,
            workspace["public_id"],
            headers,
            provider="website",
            provider_config={
                "field_mapping": {
                    "name": "contact.fullName",
                    "email": "contact.emailAddress",
                    "interest": "form.selectedProduct",
                }
            },
        )
        credential = _rotate_key(
            client, workspace["public_id"], source["public_id"], headers
        )

        response = client.post(
            f"/api/v1/external/integrations/{source['public_id']}/intake",
            headers={"X-Nexyra-Intake-Key": credential["intake_key"]},
            json={
                "contact": {
                    "fullName": "Lead Mapeado",
                    "emailAddress": "mapeado@example.com",
                },
                "form": {"selectedProduct": "Atlas"},
            },
        )

        assert response.status_code == 200
        assert response.json()["source"] == "website"
        assert response.json()["channel"] == "form"



def test_external_intake_requires_mappable_name() -> None:
    for client, _ in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(client, workspace["public_id"], headers)
        credential = _rotate_key(
            client, workspace["public_id"], source["public_id"], headers
        )

        response = client.post(
            f"/api/v1/external/integrations/{source['public_id']}/intake",
            headers={"X-Nexyra-Intake-Key": credential["intake_key"]},
            json={"email": "sem-nome@example.com"},
        )

        assert response.status_code == 422
        assert "nome do lead" in response.json()["detail"]

def test_inactive_source_and_revoked_key_block_external_intake() -> None:
    for client, _ in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(client, workspace["public_id"], headers)
        credential = _rotate_key(
            client, workspace["public_id"], source["public_id"], headers
        )
        endpoint = f"/api/v1/external/integrations/{source['public_id']}/intake"
        key_headers = {"X-Nexyra-Intake-Key": credential["intake_key"]}

        disabled = client.post(
            (
                f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
                f"{source['public_id']}/deactivate"
            ),
            headers=headers,
        )
        assert disabled.status_code == 200
        blocked = client.post(endpoint, headers=key_headers, json={"name": "Lead"})
        assert blocked.status_code == 409

        client.post(
            (
                f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
                f"{source['public_id']}/activate"
            ),
            headers=headers,
        )
        revoked = client.delete(
            (
                f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
                f"{source['public_id']}/external-key"
            ),
            headers=headers,
        )
        assert revoked.status_code == 200
        assert revoked.json()["external_intake_enabled"] is False

        after_revoke = client.post(
            endpoint,
            headers=key_headers,
            json={"name": "Lead"},
        )
        assert after_revoke.status_code == 401


def test_rotating_key_invalidates_previous_key() -> None:
    for client, _ in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(client, workspace["public_id"], headers)
        first = _rotate_key(
            client, workspace["public_id"], source["public_id"], headers
        )
        second = _rotate_key(
            client, workspace["public_id"], source["public_id"], headers
        )
        endpoint = f"/api/v1/external/integrations/{source['public_id']}/intake"

        old = client.post(
            endpoint,
            headers={"X-Nexyra-Intake-Key": first["intake_key"]},
            json={"name": "Lead Antigo"},
        )
        assert old.status_code == 401

        current = client.post(
            endpoint,
            headers={"X-Nexyra-Intake-Key": second["intake_key"]},
            json={"name": "Lead Atual"},
        )
        assert current.status_code == 200


def test_provider_without_external_intake_cannot_generate_key() -> None:
    for client, _ in _client_fixture():
        workspace, headers = _bootstrap_admin(client)
        source = _create_source(
            client,
            workspace["public_id"],
            headers,
            provider="csv",
        )

        response = client.post(
            (
                f"/api/v1/workspaces/{workspace['public_id']}/integrations/"
                f"{source['public_id']}/external-key/rotate"
            ),
            headers=headers,
        )
        assert response.status_code == 422
