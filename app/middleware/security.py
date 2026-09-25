from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Final
from uuid import uuid4

from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.security.rate_limit import RedisRateLimiter

_REQUEST_ID_HEADER: Final = "X-Request-ID"


@dataclass(frozen=True, slots=True)
class _RouteLimit:
    method: str
    path: str
    requests_per_minute: int


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adiciona headers defensivos sem depender de proxy externo."""

    def __init__(
        self,
        app: object,
        *,
        hsts_enabled: bool = False,
        hsts_max_age_seconds: int = 31_536_000,
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
    ) -> None:
        super().__init__(app)
        self.hsts_enabled = hsts_enabled
        self.hsts_max_age_seconds = hsts_max_age_seconds
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = self._request_id(request)
        request.state.request_id = request_id

        response = await call_next(request)
        headers = response.headers
        headers[_REQUEST_ID_HEADER] = request_id
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "no-referrer"
        headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        headers["Cross-Origin-Resource-Policy"] = "same-site"

        if request.url.path.startswith("/api/v1/auth"):
            headers["Cache-Control"] = "no-store"
            headers["Pragma"] = "no-cache"

        if self.hsts_enabled and request.url.scheme == "https":
            hsts = f"max-age={self.hsts_max_age_seconds}"
            if self.hsts_include_subdomains:
                hsts += "; includeSubDomains"
            if self.hsts_preload:
                hsts += "; preload"
            headers["Strict-Transport-Security"] = hsts

        return response

    @staticmethod
    def _request_id(request: Request) -> str:
        supplied = request.headers.get(_REQUEST_ID_HEADER, "").strip()
        if supplied and len(supplied) <= 64 and all(
            char.isalnum() or char in "-_." for char in supplied
        ):
            return supplied
        return uuid4().hex


class SensitiveRouteRateLimitMiddleware(BaseHTTPMiddleware):
    """Redis compartilhado no Business; memória apenas para execução local."""

    _WINDOW_SECONDS: Final = 60.0

    def __init__(
        self,
        app: object,
        *,
        enabled: bool,
        api_prefix: str,
        login_per_minute: int,
        recovery_request_per_minute: int,
        recovery_reset_per_minute: int,
        change_password_per_minute: int,
        external_intake_per_minute: int = 120,
        backend: str = "memory",
        redis_url: str = "",
        redis_prefix: str = "nexyra:rate-limit",
    ) -> None:
        super().__init__(app)
        prefix = api_prefix.rstrip("/")
        self.enabled = enabled
        if backend not in {"memory", "redis"}:
            raise ValueError("Backend de rate limit inválido.")
        self.shared = (
            RedisRateLimiter(redis_url, redis_prefix)
            if enabled and backend == "redis"
            else None
        )
        self.api_prefix = prefix
        self.external_intake_per_minute = external_intake_per_minute
        self.limits = {
            (rule.method, rule.path): rule.requests_per_minute
            for rule in (
                _RouteLimit(
                    "POST",
                    f"{prefix}/auth/login",
                    login_per_minute,
                ),
                _RouteLimit(
                    "POST",
                    f"{prefix}/auth/password-recovery/request",
                    recovery_request_per_minute,
                ),
                _RouteLimit(
                    "POST",
                    f"{prefix}/auth/password-recovery/reset",
                    recovery_reset_per_minute,
                ),
                _RouteLimit(
                    "POST",
                    f"{prefix}/auth/change-password",
                    change_password_per_minute,
                ),
            )
        }
        self._buckets: dict[tuple[str, str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if not self.enabled:
            return await call_next(request)

        route_key = (request.method.upper(), request.url.path)
        limit = self.limits.get(route_key)
        if (
            limit is None
            and route_key[0] == "POST"
            and route_key[1].startswith(
                f"{self.api_prefix}/external/integrations/"
            )
            and route_key[1].endswith("/intake")
        ):
            limit = self.external_intake_per_minute
        if (
            limit is None
            and route_key[0] == "POST"
            and route_key[1]
            in {
                f"{self.api_prefix}/meta/webhook",
                f"{self.api_prefix}/whatsapp/webhook",
            }
        ):
            limit = self.external_intake_per_minute
        if limit is None:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        key = (client_host, route_key[0], route_key[1])
        if self.shared is not None:
            try:
                allowed, retry_after = await run_in_threadpool(
                    self.shared.consume, key, limit
                )
            except RedisError:
                # Fail closed without exposing a Redis URL or its credentials.
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Proteção temporariamente indisponível."},
                    headers={"Retry-After": "5"},
                )
        else:
            allowed, retry_after = self._consume(key, limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Muitas solicitações. Aguarde antes de tentar novamente."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    def _consume(
        self,
        key: tuple[str, str, str],
        limit: int,
    ) -> tuple[bool, int]:
        now = monotonic()
        cutoff = now - self._WINDOW_SECONDS

        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                remaining = self._WINDOW_SECONDS - (now - bucket[0])
                return False, max(1, int(remaining) + 1)

            bucket.append(now)
            return True, 0
