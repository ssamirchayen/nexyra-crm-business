import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import Settings
from app.middleware.security import SensitiveRouteRateLimitMiddleware
from app.security.rate_limit import RedisRateLimiter
from app.security.runtime import validate_runtime_security


@pytest.fixture
def limiters():
    """Same Lua script against fakeredis locally or real Redis in Docker checks."""
    server = fakeredis.FakeServer()
    url = os.environ.get("RATE_LIMIT_TEST_REDIS_URL")
    prefix = "nexyra:test:" + uuid4().hex
    instances = [RedisRateLimiter(url or "redis://localhost", prefix) for _ in range(2)]
    if not url:
        for instance in instances:
            instance.client.close()
            instance.client = fakeredis.FakeRedis(server=server)
    try:
        yield instances
    finally:
        keys = list(instances[0].client.scan_iter(match=prefix + ":*"))
        if keys:
            instances[0].client.delete(*keys)
        for instance in instances:
            instance.client.close()


def test_two_workers_share_limit_and_expiring_keys(limiters):
    first, second = limiters
    key = ("192.0.2.1", "POST", "/login")
    assert first.consume(key, 2) == (True, 0)
    assert second.consume(key, 2) == (True, 0)
    allowed, retry = first.consume(key, 2)
    assert not allowed and 1 <= retry <= 60
    keys = list(first.client.scan_iter(match=first.prefix + ":*"))
    assert len(keys) == 1
    assert b"192.0.2.1" not in keys[0]
    assert 0 < first.client.pttl(keys[0]) <= 60000


def test_concurrent_consumption_is_atomic(limiters):
    def consume(index):
        return limiters[index % 2].consume(("same-ip", "POST", "/login"), 7)[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(consume, range(40))) == 7


def test_clients_and_routes_have_independent_buckets(limiters):
    limiter = limiters[0]
    assert limiter.consume(("one", "POST", "/login"), 1)[0]
    assert not limiter.consume(("one", "POST", "/login"), 1)[0]
    assert limiter.consume(("two", "POST", "/login"), 1)[0]
    assert limiter.consume(("one", "POST", "/reset"), 1)[0]


def test_expired_entries_release_capacity(limiters):
    limiter = limiters[0]
    key = ("one", "POST", "/login")
    limiter.consume(key, 1)
    redis_key = next(limiter.client.scan_iter(match=limiter.prefix + ":*"))
    member = limiter.client.zrange(redis_key, 0, 0)[0]
    limiter.client.zadd(redis_key, {member: 0})
    assert limiter.consume(key, 1) == (True, 0)
    assert limiter.client.zcard(redis_key) == 1


def app_with_limiter(enabled=True):
    app = FastAPI()
    app.add_middleware(
        SensitiveRouteRateLimitMiddleware,
        enabled=enabled,
        backend="redis",
        redis_url="redis://localhost",
        api_prefix="/api/v1",
        login_per_minute=2,
        recovery_request_per_minute=2,
        recovery_reset_per_minute=2,
        change_password_per_minute=2,
    )

    @app.post("/api/v1/auth/login")
    def login():
        return {"ok": True}

    @app.get("/api/v1/health")
    def health():
        return {"ok": True}

    return app


def test_redis_outage_fails_closed_only_on_protected_routes(monkeypatch):
    def unavailable(*args):
        raise RedisConnectionError("sensitive-connection-details")

    monkeypatch.setattr(RedisRateLimiter, "consume", unavailable)
    with TestClient(app_with_limiter()) as client:
        response = client.post("/api/v1/auth/login")
        assert response.status_code == 503
        assert response.headers["retry-after"] == "5"
        assert "sensitive" not in response.text
        assert client.get("/api/v1/health").status_code == 200
    with TestClient(app_with_limiter(enabled=False)) as client:
        assert client.post("/api/v1/auth/login").status_code == 200


def test_middleware_shares_budget_and_ignores_untrusted_forwarded_header(
    limiters, monkeypatch
):
    # Independent ASGI instances represent workers sharing a Redis server.
    original = RedisRateLimiter.consume

    def shared(self, key, limit):
        return original(limiters[0], key, limit)

    monkeypatch.setattr(RedisRateLimiter, "consume", shared)
    with TestClient(app_with_limiter()) as a, TestClient(app_with_limiter()) as b:
        assert a.post("/api/v1/auth/login").status_code == 200
        assert b.post("/api/v1/auth/login").status_code == 200
        response = a.post(
            "/api/v1/auth/login", headers={"X-Forwarded-For": "another-ip"}
        )
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) >= 1


@pytest.mark.parametrize(
    "changes",
    [
        {"security_rate_limit_backend": "invalid"},
        {"security_rate_limit_backend": "redis", "security_rate_limit_redis_url": ""},
        {
            "security_rate_limit_backend": "redis",
            "security_rate_limit_redis_url": "https://bad",
        },
        {"environment": "production", "security_rate_limit_backend": "memory"},
    ],
)
def test_invalid_limiter_configuration_is_rejected(changes):
    settings = Settings(_env_file=None, security_rate_limit_enabled=True, **changes)
    with pytest.raises(RuntimeError, match="SECURITY_RATE_LIMIT"):
        validate_runtime_security(settings)
