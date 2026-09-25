from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AuditEvent, Lead, LeadImportJob

ADMIN_PASSWORD = "Nexyra@Import123"
ADMIN_FINAL_PASSWORD = "Nexyra@Import456"


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
        with TestClient(app) as test_client:
            yield test_client, testing_session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _bootstrap_admin(client: TestClient) -> tuple[dict[str, object], dict[str, str]]:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Nexyra Import",
            "slug": "nexyra-import",
            "segment": "generic",
        },
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()

    created = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/members",
        json={
            "name": "Import Admin",
            "email": "import-admin@nexyra.demo",
            "role": "admin",
            "initial_password": ADMIN_PASSWORD,
        },
    )
    assert created.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "import-admin@nexyra.demo",
            "password": ADMIN_PASSWORD,
        },
    )
    assert login.status_code == 200
    temporary_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }
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
            "email": "import-admin@nexyra.demo",
            "password": ADMIN_FINAL_PASSWORD,
        },
    )
    assert relogin.status_code == 200
    headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}
    return workspace, headers


def _create_csv_source(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations",
        headers=headers,
        json={
            "provider": "csv",
            "name": "Planilha comercial",
            "source": "planilha",
            "channel": "importacao",
            "default_campaign": "Base Setembro",
            "routing_config": {},
            "provider_config": {},
            "active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def _base_request(csv_text: str) -> dict[str, object]:
    return {
        "filename": "leads.csv",
        "csv_text": csv_text,
        "delimiter": "auto",
        "duplicate_mode": "update",
        "source": "csv",
        "channel": "import",
        "campaign": None,
        "default_status": None,
        "default_priority": "media",
        "consent_default": True,
        "field_mapping": {},
    }


def test_options_list_active_csv_sources(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _create_csv_source(client, workspace["public_id"], headers)

    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/options",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["max_rows"] == 5000
    assert payload["sources"][0]["public_id"] == source["public_id"]
    assert "name" in payload["supported_fields"]


def test_preview_auto_detects_semicolon_and_portuguese_headers(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    request = _base_request(
        "Nome;Telefone;E-mail;Interesse\n"
        "Maria;(92) 99999-1111;maria@example.com;Atlas\n"
        "João;92988882222;joao@example.com;CRM\n"
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/preview",
        headers=headers,
        json=request,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["delimiter"] == ";"
    assert payload["total_rows"] == 2
    assert payload["valid_rows"] == 2
    assert payload["invalid_rows"] == 0
    assert payload["field_mapping"]["name"] == "Nome"
    assert payload["field_mapping"]["phone"] == "Telefone"
    assert payload["field_mapping"]["email"] == "E-mail"


def test_execute_uses_csv_source_defaults_and_creates_job(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, testing_session = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = _create_csv_source(client, workspace["public_id"], headers)
    request = _base_request(
        "nome,email,interesse\n"
        "Ana,ana@example.com,Atlas\n"
        "Bruno,bruno@example.com,CRM\n"
    )
    request["integration_public_id"] = source["public_id"]

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/execute",
        headers=headers,
        json=request,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] == 2
    assert payload["duplicate_updated"] == 0
    assert payload["failed"] == 0
    assert payload["job"]["source"] == "planilha"
    assert payload["job"]["channel"] == "importacao"
    assert payload["job"]["campaign"] == "Base Setembro"

    with testing_session() as db:
        leads = list(db.scalars(select(Lead).order_by(Lead.id.asc())).all())
        assert len(leads) == 2
        assert all(item.source == "planilha" for item in leads)
        assert all(item.channel == "importacao" for item in leads)
        assert all(item.campaign == "Base Setembro" for item in leads)

        job = db.scalar(select(LeadImportJob))
        assert job is not None
        assert job.status == "completed"
        assert job.created_count == 2

        event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_public_id == job.public_id,
                AuditEvent.action == "lead_import.completed",
            )
        )
        assert event is not None
        assert event.actor_type == "user"


def test_duplicate_mode_update_updates_existing_lead(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    endpoint = f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/execute"

    first = _base_request("nome,email,interesse\nMaria,maria@example.com,Atlas\n")
    response = client.post(endpoint, headers=headers, json=first)
    assert response.status_code == 200
    assert response.json()["created"] == 1

    second = _base_request(
        "nome,email,interesse\nMaria Nova,maria@example.com,Nexyra\n"
    )
    response = client.post(endpoint, headers=headers, json=second)
    assert response.status_code == 200
    assert response.json()["duplicate_updated"] == 1

    leads = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=headers,
    ).json()
    assert len(leads) == 1
    assert leads[0]["name"] == "Maria Nova"
    assert leads[0]["interest"] == "Nexyra"


def test_duplicate_mode_skip_keeps_existing_lead_unchanged(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    endpoint = f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/execute"

    first = _base_request("nome,email,interesse\nMaria,maria@example.com,Atlas\n")
    assert client.post(endpoint, headers=headers, json=first).status_code == 200

    second = _base_request(
        "nome,email,interesse\nMaria Nova,maria@example.com,Nexyra\n"
    )
    second["duplicate_mode"] = "skip"
    response = client.post(endpoint, headers=headers, json=second)

    assert response.status_code == 200
    assert response.json()["duplicate_skipped"] == 1
    leads = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=headers,
    ).json()
    assert len(leads) == 1
    assert leads[0]["name"] == "Maria"
    assert leads[0]["interest"] == "Atlas"


def test_invalid_rows_are_reported_without_blocking_valid_rows(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    request = _base_request(
        "nome,email\n"
        "Lead Válido,valido@example.com\n"
        ",semnome@example.com\n"
        "Email Ruim,email-invalido\n"
    )

    preview = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/preview",
        headers=headers,
        json=request,
    )
    assert preview.status_code == 200
    assert preview.json()["valid_rows"] == 1
    assert preview.json()["invalid_rows"] == 2

    executed = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/execute",
        headers=headers,
        json=request,
    )
    assert executed.status_code == 200
    assert executed.json()["created"] == 1
    assert executed.json()["failed"] == 2
    assert len(executed.json()["error_samples"]) == 2
    assert executed.json()["job"]["status"] == "completed_with_errors"


def test_explicit_mapping_supports_unknown_column_names(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    request = _base_request(
        "Pessoa,Contato,Oferta\n"
        "Carlos,carlos@example.com,Plano Pro\n"
    )
    request["field_mapping"] = {
        "name": "Pessoa",
        "email": "Contato",
        "interest": "Oferta",
    }

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/execute",
        headers=headers,
        json=request,
    )

    assert response.status_code == 200
    assert response.json()["created"] == 1
    lead = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/leads",
        headers=headers,
    ).json()[0]
    assert lead["name"] == "Carlos"
    assert lead["interest"] == "Plano Pro"


def test_non_csv_integration_source_is_rejected(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    source = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/integrations",
        headers=headers,
        json={
            "provider": "webhook",
            "name": "Webhook",
            "source": "webhook",
            "channel": "webhook",
        },
    ).json()
    request = _base_request("nome,email\nTeste,teste@example.com\n")
    request["integration_public_id"] = source["public_id"]

    response = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/preview",
        headers=headers,
        json=request,
    )

    assert response.status_code == 422
    assert "Importação CSV" in response.json()["detail"]


def test_import_history_is_scoped_to_workspace(
    client_and_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = client_and_session
    workspace, headers = _bootstrap_admin(client)
    request = _base_request("nome,email\nTeste,teste@example.com\n")
    executed = client.post(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports/execute",
        headers=headers,
        json=request,
    )
    assert executed.status_code == 200

    response = client.get(
        f"/api/v1/workspaces/{workspace['public_id']}/lead-imports",
        headers=headers,
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["filename"] == "leads.csv"
