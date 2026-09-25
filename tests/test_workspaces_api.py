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


def test_create_workspace(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Loja Nexyra Demo",
            "slug": "loja-nexyra-demo",
            "segment": "retail",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["public_id"].startswith("WS-")
    assert payload["slug"] == "loja-nexyra-demo"
    assert payload["active"] is True


def test_list_get_update_and_deactivate(client: TestClient) -> None:
    created = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Auto Nexyra",
            "slug": "auto-nexyra",
            "segment": "automotive",
        },
    ).json()

    assert len(client.get("/api/v1/workspaces").json()) == 1

    public_id = created["public_id"]
    assert client.get(f"/api/v1/workspaces/{public_id}").status_code == 200

    updated = client.patch(
        f"/api/v1/workspaces/{public_id}",
        json={"name": "Auto Nexyra Prime"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Auto Nexyra Prime"

    deactivated = client.post(
        f"/api/v1/workspaces/{public_id}/deactivate"
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False


def test_duplicate_slug_returns_409(client: TestClient) -> None:
    payload = {
        "name": "Empresa A",
        "slug": "empresa-unica",
        "segment": "generic",
    }
    assert client.post("/api/v1/workspaces", json=payload).status_code == 201

    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Empresa B",
            "slug": "empresa-unica",
            "segment": "services",
        },
    )
    assert response.status_code == 409


def test_invalid_slug_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Empresa Teste",
            "slug": "Empresa Teste !!!",
            "segment": "generic",
        },
    )
    assert response.status_code == 422


def test_missing_workspace_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces/WS-INEXISTENTE")
    assert response.status_code == 404
