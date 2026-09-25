from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.security import (
    SecurityHeadersMiddleware,
    SensitiveRouteRateLimitMiddleware,
)


def _security_headers_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/v1/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    def login() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_security_headers_and_request_id() -> None:
    client = TestClient(_security_headers_app())
    response = client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "req-test-123"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-test-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in response.headers["permissions-policy"]


def test_invalid_request_id_is_replaced() -> None:
    client = TestClient(_security_headers_app())
    response = client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "invalid id with spaces"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "invalid id with spaces"
    assert len(response.headers["x-request-id"]) == 32


def test_auth_responses_are_not_cacheable() -> None:
    client = TestClient(_security_headers_app())
    response = client.post("/api/v1/auth/login")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def _rate_limited_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        SensitiveRouteRateLimitMiddleware,
        enabled=True,
        api_prefix="/api/v1",
        login_per_minute=2,
        recovery_request_per_minute=2,
        recovery_reset_per_minute=2,
        change_password_per_minute=2,
        external_intake_per_minute=2,
    )

    @app.post("/api/v1/auth/login")
    def login() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/external/integrations/INT-TEST/intake")
    def external_intake() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/meta/webhook")
    def meta_webhook() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_sensitive_route_rate_limit_returns_429() -> None:
    client = TestClient(_rate_limited_app())

    assert client.post("/api/v1/auth/login").status_code == 200
    assert client.post("/api/v1/auth/login").status_code == 200
    blocked = client.post("/api/v1/auth/login")

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


def test_non_sensitive_route_is_not_rate_limited() -> None:
    client = TestClient(_rate_limited_app())
    for _ in range(5):
        assert client.get("/api/v1/health").status_code == 200


def test_external_intake_is_rate_limited() -> None:
    client = TestClient(_rate_limited_app())
    path = "/api/v1/external/integrations/INT-TEST/intake"

    assert client.post(path).status_code == 200
    assert client.post(path).status_code == 200
    blocked = client.post(path)

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


def test_meta_webhook_is_rate_limited() -> None:
    client = TestClient(_rate_limited_app())
    path = "/api/v1/meta/webhook"

    assert client.post(path).status_code == 200
    assert client.post(path).status_code == 200
    blocked = client.post(path)

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
