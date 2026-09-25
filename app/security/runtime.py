from __future__ import annotations

from collections.abc import Iterable

from app.core.config import Settings

_PRODUCTION_NAMES = {"prod", "production"}
_DEFAULT_ATLAS_TOKEN = "dev-nexyra-atlas-token"
_DEFAULT_INTEGRATION_SECRET_KEY = "dev-only-nexyra-integration-secret-key"


def parse_csv_setting(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def is_production_environment(value: str) -> bool:
    return value.strip().lower() in _PRODUCTION_NAMES


def _append_if(errors: list[str], condition: bool, message: str) -> None:
    if condition:
        errors.append(message)


def _validate_positive(name: str, value: int, errors: list[str]) -> None:
    _append_if(errors, value <= 0, f"{name} deve ser maior que zero.")


def _missing_any(values: Iterable[str]) -> bool:
    return any(not value.strip() for value in values)


def validate_runtime_security(settings: Settings) -> None:
    """Falha cedo quando a configuração de segurança é incoerente.

    Em desenvolvimento a configuração local continua simples. Em produção,
    defaults inseguros conhecidos são recusados para evitar subir o CRM com
    token de integração de exemplo, CORS aberto ou recuperação via console.
    """

    errors: list[str] = []

    _append_if(
        errors,
        settings.security_rate_limit_backend not in {"memory", "redis"},
        "SECURITY_RATE_LIMIT_BACKEND deve ser memory ou redis.",
    )
    if (
        settings.security_rate_limit_enabled
        and settings.security_rate_limit_backend == "redis"
    ):
        _append_if(
            errors,
            not settings.security_rate_limit_redis_url.startswith(
                ("redis://", "rediss://")
            ),
            "SECURITY_RATE_LIMIT_REDIS_URL deve usar redis:// ou rediss://.",
        )
        _append_if(
            errors,
            not settings.security_rate_limit_redis_prefix.strip(),
            "SECURITY_RATE_LIMIT_REDIS_PREFIX não pode ficar vazio.",
        )

    cors_origins = parse_csv_setting(settings.cors_origins)
    allowed_hosts = parse_csv_setting(settings.security_allowed_hosts)

    _append_if(errors, not cors_origins, "CORS_ORIGINS não pode ficar vazio.")
    _append_if(
        errors,
        not allowed_hosts,
        "SECURITY_ALLOWED_HOSTS não pode ficar vazio.",
    )

    _validate_positive(
        "AUTH_SESSION_HOURS",
        settings.auth_session_hours,
        errors,
    )
    _validate_positive(
        "AUTH_PASSWORD_ITERATIONS",
        settings.auth_password_iterations,
        errors,
    )
    _validate_positive(
        "SECURITY_LOGIN_REQUESTS_PER_MINUTE",
        settings.security_login_requests_per_minute,
        errors,
    )
    _validate_positive(
        "SECURITY_PASSWORD_RECOVERY_REQUESTS_PER_MINUTE",
        settings.security_password_recovery_requests_per_minute,
        errors,
    )
    _validate_positive(
        "SECURITY_PASSWORD_RESET_REQUESTS_PER_MINUTE",
        settings.security_password_reset_requests_per_minute,
        errors,
    )
    _validate_positive(
        "SECURITY_CHANGE_PASSWORD_REQUESTS_PER_MINUTE",
        settings.security_change_password_requests_per_minute,
        errors,
    )
    _validate_positive(
        "SECURITY_EXTERNAL_INTAKE_REQUESTS_PER_MINUTE",
        settings.security_external_intake_requests_per_minute,
        errors,
    )

    if is_production_environment(settings.environment):
        _append_if(
            errors,
            settings.security_rate_limit_backend != "redis",
            "SECURITY_RATE_LIMIT_BACKEND deve ser redis em produção.",
        )
        _append_if(
            errors,
            not settings.security_rate_limit_enabled,
            "SECURITY_RATE_LIMIT_ENABLED deve estar ativo em produção.",
        )
        _append_if(
            errors,
            "*" in cors_origins,
            "CORS_ORIGINS não pode conter '*' em produção.",
        )
        _append_if(
            errors,
            "*" in allowed_hosts,
            "SECURITY_ALLOWED_HOSTS não pode conter '*' em produção.",
        )

        if settings.security_require_strong_secrets_in_production:
            atlas_token = settings.atlas_integration_token.strip()
            _append_if(
                errors,
                atlas_token == _DEFAULT_ATLAS_TOKEN or len(atlas_token) < 32,
                (
                    "ATLAS_INTEGRATION_TOKEN deve ser substituído por um "
                    "segredo com pelo menos 32 caracteres em produção."
                ),
            )
            integration_secret_key = settings.integration_secret_master_key.strip()
            _append_if(
                errors,
                integration_secret_key == _DEFAULT_INTEGRATION_SECRET_KEY
                or len(integration_secret_key) < 32,
                (
                    "INTEGRATION_SECRET_MASTER_KEY deve ser substituída por um "
                    "segredo com pelo menos 32 caracteres em produção."
                ),
            )

        delivery = settings.auth_password_reset_delivery.strip().lower()
        _append_if(
            errors,
            delivery == "console",
            (
                "AUTH_PASSWORD_RESET_DELIVERY=console é permitido apenas "
                "em desenvolvimento; configure SMTP em produção."
            ),
        )
        if delivery == "smtp":
            _append_if(
                errors,
                _missing_any(
                    [
                        settings.auth_smtp_host,
                        settings.auth_smtp_from,
                    ]
                ),
                (
                    "AUTH_SMTP_HOST e AUTH_SMTP_FROM são obrigatórios "
                    "quando a recuperação usa SMTP."
                ),
            )

    if errors:
        details = "\n - ".join(errors)
        raise RuntimeError(
            "Configuração de segurança inválida do Nexyra CRM:\n - " + details
        )
