from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db.runtime import (
    build_engine_configuration,
    database_backend,
    normalize_database_url,
    validate_database_runtime,
)


def test_normalizes_postgres_urls_to_psycopg() -> None:
    assert normalize_database_url("postgres://u:p@db:5432/name") == (
        "postgresql+psycopg://u:p@db:5432/name"
    )
    assert normalize_database_url("postgresql://u:p@db/name") == (
        "postgresql+psycopg://u:p@db/name"
    )


def test_postgres_engine_uses_business_pool() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://u:p@db/name",
        database_pool_size=12,
        database_max_overflow=24,
        database_pool_timeout_seconds=31,
        database_pool_recycle_seconds=901,
        database_connect_timeout_seconds=7,
    )
    url, options = build_engine_configuration(settings)
    assert database_backend(url) == "postgresql"
    assert options["pool_size"] == 12
    assert options["max_overflow"] == 24
    assert options["pool_timeout"] == 31
    assert options["pool_recycle"] == 901
    assert options["connect_args"]["connect_timeout"] == 7


def test_sqlite_keeps_thread_compatibility_for_tests() -> None:
    settings = Settings(database_url="sqlite:///:memory:")
    _, options = build_engine_configuration(settings)
    assert options["connect_args"]["check_same_thread"] is False
    assert "pool_size" not in options


def test_business_can_require_postgresql() -> None:
    settings = Settings(
        database_url="sqlite:///./local.db",
        database_require_postgresql=True,
    )
    with pytest.raises(RuntimeError, match="exige PostgreSQL"):
        validate_database_runtime(settings)
