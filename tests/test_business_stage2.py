import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.core.config import get_settings


@pytest.mark.parametrize('password', ['abc@db', 'a:b/c?#%+$', 'senha simples'])
def test_password_components_roundtrip(monkeypatch, password):
    monkeypatch.setenv('NEXYRA_DB_HOST', 'db')
    monkeypatch.setenv('NEXYRA_DB_PASSWORD', password)
    get_settings.cache_clear()
    try:
        url = make_url(get_settings().database_url)
        assert url.host == 'db'
        assert url.password == password
        assert url.get_driver_name() == 'psycopg'
    finally:
        get_settings.cache_clear()


def test_empty_password_fails_closed(monkeypatch):
    monkeypatch.setenv('NEXYRA_DB_HOST', 'db')
    monkeypatch.setenv('NEXYRA_DB_PASSWORD', '')
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match='NEXYRA_DB_PASSWORD'):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_native_database_config_preserved(monkeypatch):
    monkeypatch.delenv('NEXYRA_DB_HOST', raising=False)
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///native.db')
    get_settings.cache_clear()
    try:
        assert get_settings().database_url == 'sqlite:///native.db'
    finally:
        get_settings.cache_clear()


def test_first_access_idempotent(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, DATABASE_URL=f'sqlite:///{tmp_path / "test.db"}',
               DATABASE_REQUIRE_POSTGRESQL='false', AUTH_PASSWORD_ITERATIONS='1000')
    env.pop('NEXYRA_DB_HOST', None)
    setup = 'from app.db.base import Base; import app.models; from app.db.session import engine; Base.metadata.create_all(engine)'
    subprocess.run([sys.executable, '-c', setup], cwd=root, env=env, check=True, capture_output=True)
    command = [sys.executable, 'tools/business_first_access.py']
    first = subprocess.run(command, cwd=root, env=env, check=True, capture_output=True, text=True)
    assert 'Senha temporária:' in first.stdout
    second = subprocess.run(command, cwd=root, env=env, check=True, capture_output=True, text=True)
    assert 'Nenhum acesso foi alterado' in second.stdout
    assert 'Senha temporária:' not in second.stdout
