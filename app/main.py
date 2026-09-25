from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.activities import router as activities_router
from app.api.routes.atlas_integration import router as atlas_integration_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.communication import router as communication_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.inbox import router as inbox_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.lead_batch import router as lead_batch_router
from app.api.routes.lead_cadences import router as lead_cadences_router
from app.api.routes.lead_distribution import router as lead_distribution_router
from app.api.routes.lead_imports import router as lead_imports_router
from app.api.routes.lead_recommendations import router as lead_recommendations_router
from app.api.routes.lead_sla import router as lead_sla_router
from app.api.routes.leads import router as leads_router
from app.api.routes.meta_integrations import router as meta_integrations_router
from app.api.routes.opportunities import router as opportunities_router
from app.api.routes.reports import router as reports_router
from app.api.routes.segments import router as segments_router
from app.api.routes.users import router as users_router
from app.api.routes.whatsapp_bulk import router as whatsapp_bulk_router
from app.api.routes.whatsapp_integrations import router as whatsapp_integrations_router
from app.api.routes.workspaces import router as workspaces_router
from app.core.config import get_settings
from app.db.runtime import validate_database_runtime
from app.middleware.security import (
    SecurityHeadersMiddleware,
    SensitiveRouteRateLimitMiddleware,
)
from app.security.runtime import (
    is_production_environment,
    parse_csv_setting,
    validate_runtime_security,
)

settings = get_settings()
validate_runtime_security(settings)
validate_database_runtime(settings)

production = is_production_environment(settings.environment)
docs_enabled = not (
    production and settings.security_disable_docs_in_production
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API oficial do Nexyra CRM — plataforma comercial "
        "multiempresa e multissegmento."
    ),
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

cors_origins = parse_csv_setting(settings.cors_origins)
allowed_hosts = parse_csv_setting(settings.security_allowed_hosts)

# Em desenvolvimento, o Vite pode subir em 5174/5175 quando 5173 já está
# ocupada. Aceitamos somente loopback local em qualquer porta para não
# bloquear o login durante desenvolvimento. Em produção, continua valendo
# exclusivamente a lista explícita de CORS_ORIGINS.
local_development_origin_regex = (
    r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$"
    if not production
    else None
)

# CORS restrito aos verbos e cabeçalhos realmente usados pelo CRM.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=local_development_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",
        "X-Nexyra-Intake-Key",
        "X-Idempotency-Key",
    ],
    expose_headers=["X-Request-ID", "Retry-After"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts,
)

app.add_middleware(
    SensitiveRouteRateLimitMiddleware,
    enabled=settings.security_rate_limit_enabled,
    backend=settings.security_rate_limit_backend,
    redis_url=settings.security_rate_limit_redis_url,
    redis_prefix=settings.security_rate_limit_redis_prefix,
    api_prefix=settings.api_prefix,
    login_per_minute=settings.security_login_requests_per_minute,
    recovery_request_per_minute=(
        settings.security_password_recovery_requests_per_minute
    ),
    recovery_reset_per_minute=settings.security_password_reset_requests_per_minute,
    change_password_per_minute=(
        settings.security_change_password_requests_per_minute
    ),
    external_intake_per_minute=(
        settings.security_external_intake_requests_per_minute
    ),
)

# Adicionado por último para envolver inclusive respostas 4xx/429 geradas
# pelos middlewares internos.
app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_enabled=settings.security_hsts_enabled,
    hsts_max_age_seconds=settings.security_hsts_max_age_seconds,
    hsts_include_subdomains=settings.security_hsts_include_subdomains,
    hsts_preload=settings.security_hsts_preload,
)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(workspaces_router, prefix=settings.api_prefix)
app.include_router(segments_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(leads_router, prefix=settings.api_prefix)
app.include_router(lead_batch_router, prefix=settings.api_prefix)
app.include_router(communication_router, prefix=settings.api_prefix)
app.include_router(lead_distribution_router, prefix=settings.api_prefix)
app.include_router(lead_cadences_router, prefix=settings.api_prefix)
app.include_router(lead_sla_router, prefix=settings.api_prefix)
app.include_router(lead_imports_router, prefix=settings.api_prefix)
app.include_router(lead_recommendations_router, prefix=settings.api_prefix)
app.include_router(integrations_router, prefix=settings.api_prefix)
app.include_router(meta_integrations_router, prefix=settings.api_prefix)
app.include_router(whatsapp_integrations_router, prefix=settings.api_prefix)
app.include_router(whatsapp_bulk_router, prefix=settings.api_prefix)
app.include_router(inbox_router, prefix=settings.api_prefix)
app.include_router(opportunities_router, prefix=settings.api_prefix)
app.include_router(reports_router, prefix=settings.api_prefix)
app.include_router(activities_router, prefix=settings.api_prefix)
app.include_router(dashboard_router, prefix=settings.api_prefix)
app.include_router(audit_router, prefix=settings.api_prefix)
app.include_router(atlas_integration_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str | bool]:
    return {
        "ok": True,
        "product": settings.app_name,
        "message": "Nexyra CRM API online.",
    }
