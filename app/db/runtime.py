from __future__ import annotations

from typing import Any

from sqlalchemy.engine import make_url

from app.core.config import Settings


def normalize_database_url(database_url: str) -> str:
    value = database_url.strip()
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


def database_backend(database_url: str) -> str:
    return make_url(normalize_database_url(database_url)).get_backend_name()


def build_engine_configuration(settings: Settings) -> tuple[str, dict[str, Any]]:
    url = normalize_database_url(settings.database_url)
    backend = database_backend(url)
    options: dict[str, Any] = {
        "echo": settings.sql_echo,
        "future": True,
        "pool_pre_ping": True,
    }

    if backend == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
    elif backend == "postgresql":
        options.update(
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
            pool_recycle=settings.database_pool_recycle_seconds,
            connect_args={
                "connect_timeout": settings.database_connect_timeout_seconds,
                "application_name": settings.app_name,
            },
        )

    return url, options


def validate_database_runtime(settings: Settings) -> None:
    backend = database_backend(settings.database_url)
    if settings.database_require_postgresql and backend != "postgresql":
        raise RuntimeError(
            "Nexyra Business exige PostgreSQL neste ambiente. "
            "Configure DATABASE_URL com postgresql+psycopg://..."
        )
