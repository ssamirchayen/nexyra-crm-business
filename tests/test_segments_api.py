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


def _create_workspace(
    client: TestClient,
    *,
    name: str,
    slug: str,
    segment: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": name,
            "slug": slug,
            "segment": segment,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_segment_catalog_contains_multiple_business_types(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/segments")

    assert response.status_code == 200

    payload = response.json()
    codes = {item["code"] for item in payload}

    assert "education" in codes
    assert "real_estate" in codes
    assert "automotive" in codes
    assert "retail" in codes
    assert "wholesale" in codes
    assert "services" in codes
    assert "custom" in codes


def test_education_segment_has_education_defaults(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/segments/education")

    assert response.status_code == 200

    payload = response.json()

    assert payload["interest_label"] == "Curso"
    assert "matricula" in payload["pipeline"]
    assert "curso" in payload["custom_fields"]


def test_workspace_gets_segment_defaults(
    client: TestClient,
) -> None:
    workspace = _create_workspace(
        client,
        name="Auto Nexyra",
        slug="auto-nexyra",
        segment="automotive",
    )

    public_id = workspace["public_id"]

    response = client.get(
        f"/api/v1/workspaces/{public_id}/segment-config"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["segment_code"] == "automotive"
    assert payload["interest_label"] == "Veículo"
    assert "test_drive" in payload["pipeline"]
    assert "veiculo" in payload["custom_fields"]


def test_workspace_can_customize_pipeline_and_fields(
    client: TestClient,
) -> None:
    workspace = _create_workspace(
        client,
        name="Loja Nexyra",
        slug="loja-nexyra",
        segment="retail",
    )

    public_id = workspace["public_id"]

    response = client.put(
        f"/api/v1/workspaces/{public_id}/segment-config",
        json={
            "segment_code": "retail",
            "interest_label": "Item desejado",
            "pipeline": [
                "novo",
                "contato",
                "orcamento",
                "fechado",
            ],
            "custom_fields": [
                "produto",
                "categoria",
                "marca",
            ],
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["interest_label"] == "Item desejado"
    assert payload["pipeline"][-1] == "fechado"
    assert "marca" in payload["custom_fields"]


def test_workspace_can_change_segment(
    client: TestClient,
) -> None:
    workspace = _create_workspace(
        client,
        name="Empresa Mutável",
        slug="empresa-mutavel",
        segment="generic",
    )

    public_id = workspace["public_id"]

    response = client.put(
        f"/api/v1/workspaces/{public_id}/segment-config",
        json={
            "segment_code": "services",
        },
    )

    assert response.status_code == 200
    assert response.json()["segment_code"] == "services"

    workspace_response = client.get(
        f"/api/v1/workspaces/{public_id}"
    )

    assert workspace_response.status_code == 200
    assert workspace_response.json()["segment"] == "services"


def test_custom_segment_can_have_custom_pipeline(
    client: TestClient,
) -> None:
    workspace = _create_workspace(
        client,
        name="Negócio Personalizado",
        slug="negocio-personalizado",
        segment="generic",
    )

    public_id = workspace["public_id"]

    response = client.put(
        f"/api/v1/workspaces/{public_id}/segment-config",
        json={
            "segment_code": "custom",
            "interest_label": "Demanda",
            "pipeline": [
                "entrada",
                "analise",
                "proposta",
                "aprovado",
            ],
            "custom_fields": [
                "tipo_demanda",
                "prazo",
                "responsavel_externo",
            ],
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["segment_code"] == "custom"
    assert payload["pipeline"][0] == "entrada"
    assert "responsavel_externo" in payload["custom_fields"]


def test_unknown_segment_returns_404_in_catalog(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/segments/inexistente")

    assert response.status_code == 404


def test_unknown_segment_returns_422_for_workspace(
    client: TestClient,
) -> None:
    workspace = _create_workspace(
        client,
        name="Empresa Demo",
        slug="empresa-demo",
        segment="generic",
    )

    public_id = workspace["public_id"]

    response = client.put(
        f"/api/v1/workspaces/{public_id}/segment-config",
        json={
            "segment_code": "segmento_inexistente",
        },
    )

    assert response.status_code == 422


def test_duplicate_pipeline_stage_returns_422(
    client: TestClient,
) -> None:
    workspace = _create_workspace(
        client,
        name="Empresa Pipeline",
        slug="empresa-pipeline",
        segment="generic",
    )

    public_id = workspace["public_id"]

    response = client.put(
        f"/api/v1/workspaces/{public_id}/segment-config",
        json={
            "segment_code": "custom",
            "pipeline": [
                "novo",
                "novo",
            ],
        },
    )

    assert response.status_code == 422
