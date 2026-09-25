from fastapi.testclient import TestClient

from app.main import app


def test_business_readiness_checks_database() -> None:
    response = TestClient(app).get("/api/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["database"] == "sqlite"
    assert payload["deployment_mode"] == "business"
