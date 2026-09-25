"""Isolate automated tests before importing application engines or routes.

Compose injects live credentials even into `run --rm` containers. These tests
use disposable SQLite databases and known development settings, never the live
PostgreSQL server or the project's .env file.
"""
import os
from tempfile import TemporaryDirectory

from app.core.config import Settings, get_settings

# config.py defines settings lazily; no engine/application is imported here.
for key in list(os.environ):
    if key.lower() in Settings.model_fields or key.startswith("NEXYRA_DB_"):
        del os.environ[key]
Settings.model_config["env_file"] = None
_TEST_DIRECTORY = TemporaryDirectory(prefix="nexyra-pytest-")
os.environ["DATABASE_URL"] = "sqlite:///" + _TEST_DIRECTORY.name + "/tests.db"
get_settings.cache_clear()


def pytest_unconfigure(config):
    # Windows cannot unlink a SQLite file while pooled connections remain open.
    import sys
    session = sys.modules.get("app.db.session")
    if session is not None:
        session.engine.dispose()
    _TEST_DIRECTORY.cleanup()
