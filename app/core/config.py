from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Nexyra CRM"
    app_version: str = "1.0.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    deployment_mode: str = "business"
    database_url: str = "sqlite:///./nexyra_crm.db"
    sql_echo: bool = False
    database_require_postgresql: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1800
    database_connect_timeout_seconds: int = 10
    cors_origins: str = (
        "http://127.0.0.1:5173,http://localhost:5173"
    )

    auth_session_hours: int = 12
    auth_session_touch_minutes: int = 5
    auth_login_max_attempts: int = 5
    auth_lockout_minutes: int = 15
    auth_password_iterations: int = 600_000
    auth_password_reset_minutes: int = 30
    auth_password_reset_cooldown_seconds: int = 60
    auth_password_reset_delivery: str = "console"
    auth_password_reset_frontend_url: str = (
        "http://127.0.0.1:5173/reset-password"
    )
    auth_smtp_host: str = ""
    auth_smtp_port: int = 587
    auth_smtp_username: str = ""
    auth_smtp_password: str = ""
    auth_smtp_from: str = ""
    auth_smtp_starttls: bool = True
    auth_smtp_ssl: bool = False

    # Sprint 3 / Etapa 6 — hardening de produção.
    security_allowed_hosts: str = "127.0.0.1,localhost,testserver"
    security_rate_limit_enabled: bool = False
    security_rate_limit_backend: str = "memory"
    security_rate_limit_redis_url: str = ""
    security_rate_limit_redis_prefix: str = "nexyra:rate-limit"
    security_login_requests_per_minute: int = 30
    security_password_recovery_requests_per_minute: int = 10
    security_password_reset_requests_per_minute: int = 10
    security_change_password_requests_per_minute: int = 10
    security_external_intake_requests_per_minute: int = 120
    security_disable_docs_in_production: bool = True
    security_require_strong_secrets_in_production: bool = True
    security_hsts_enabled: bool = False
    security_hsts_max_age_seconds: int = 31_536_000
    security_hsts_include_subdomains: bool = True
    security_hsts_preload: bool = False

    # Sprint 4 / Etapa 4 — credenciais seguras + Meta Lead Ads.
    integration_secret_master_key: str = "dev-only-nexyra-integration-secret-key"
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = ""
    meta_graph_api_version: str = "v25.0"
    meta_graph_base_url: str = "https://graph.facebook.com"
    meta_http_timeout_seconds: float = 10.0

    # Sprint 4 / Etapa 5 — WhatsApp Cloud API.
    whatsapp_app_secret: str = ""
    whatsapp_webhook_verify_token: str = ""
    whatsapp_meta_app_id: str = ""
    whatsapp_embedded_signup_config_id: str = ""
    whatsapp_graph_api_version: str = "v25.0"
    whatsapp_graph_base_url: str = "https://graph.facebook.com"
    whatsapp_http_timeout_seconds: float = 10.0

    atlas_contract_version: str = "1.0"
    atlas_integration_token: str = "dev-nexyra-atlas-token"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    # Docker passes components separately so reserved password characters are safe.
    import os

    from sqlalchemy.engine import URL

    if os.environ.get("NEXYRA_DB_HOST"):
        password = os.environ.get("NEXYRA_DB_PASSWORD", "")
        if not password:
            raise ValueError("NEXYRA_DB_PASSWORD deve ser configurado.")
        url = URL.create(
            "postgresql+psycopg",
            username=os.environ.get("NEXYRA_DB_USER", "nexyra"),
            password=password,
            host=os.environ["NEXYRA_DB_HOST"],
            port=int(os.environ.get("NEXYRA_DB_PORT", "5432")),
            database=os.environ.get("NEXYRA_DB_NAME", "nexyra_business"),
        )
        return Settings(database_url=url.render_as_string(hide_password=False))
    return Settings()
