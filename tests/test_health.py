from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["product"] == "Nexyra CRM"


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    payload = response.json()

    assert payload["ok"] is True
    assert payload["product"] == "Nexyra CRM"
    assert payload["version"] == "1.0.0"
    assert payload["environment"] == "development"
