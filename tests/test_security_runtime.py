from __future__ import annotations

import pytest

from app.core.config import Settings
from app.security.runtime import (
    is_production_environment,
    parse_csv_setting,
    validate_runtime_security,
)


def test_parse_csv_setting_removes_empty_items() -> None:
    assert parse_csv_setting("a, b, ,c") == ["a", "b", "c"]


def test_production_aliases() -> None:
    assert is_production_environment("production") is True
    assert is_production_environment(" PROD ") is True
    assert is_production_environment("development") is False


def test_development_accepts_local_defaults() -> None:
    settings = Settings(_env_file=None)
    validate_runtime_security(settings)


def test_production_rejects_development_secrets_and_console_delivery() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        cors_origins="https://crm.example.com",
        security_allowed_hosts="crm.example.com",
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_security(settings)

    message = str(exc_info.value)
    assert "ATLAS_INTEGRATION_TOKEN" in message
    assert "INTEGRATION_SECRET_MASTER_KEY" in message
    assert "AUTH_PASSWORD_RESET_DELIVERY=console" in message


def test_production_accepts_explicit_secure_configuration() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        cors_origins="https://crm.example.com",
        security_allowed_hosts="api.example.com",
        security_rate_limit_enabled=True,
        security_rate_limit_backend="redis",
        security_rate_limit_redis_url="redis://localhost:6379/0",
        atlas_integration_token="x" * 48,
        integration_secret_master_key="s" * 48,
        auth_password_reset_delivery="smtp",
        auth_smtp_host="smtp.example.com",
        auth_smtp_from="no-reply@example.com",
    )
    validate_runtime_security(settings)


def test_production_requires_rate_limit_enabled() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        cors_origins="https://crm.example.com",
        security_allowed_hosts="api.example.com",
        atlas_integration_token="x" * 48,
        integration_secret_master_key="s" * 48,
        auth_password_reset_delivery="smtp",
        auth_smtp_host="smtp.example.com",
        auth_smtp_from="no-reply@example.com",
        security_rate_limit_enabled=False,
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_security(settings)

    assert "SECURITY_RATE_LIMIT_ENABLED" in str(exc_info.value)
