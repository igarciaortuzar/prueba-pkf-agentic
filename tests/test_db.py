"""Tests de la capa de conexión (`app/db.py`) contra un archivo libSQL
local. No requieren credenciales reales de Turso (ver ADR-003 y el
docstring de `app/db.py`: la conexión de producción a Turso no impide usar
un archivo local para dev/tests).
"""
from __future__ import annotations

import os

import pytest

from app.db import ConfigError, get_client, get_database_config


@pytest.fixture
def local_db_path(tmp_path):
    db_file = tmp_path / "test_local.db"
    return f"file:{db_file}"


def test_get_client_local_file_can_create_table_and_query(local_db_path):
    client = get_client(url=local_db_path)
    try:
        client.execute(
            "CREATE TABLE IF NOT EXISTS smoke_test (id INTEGER PRIMARY KEY, "
            "nombre TEXT)"
        )
        client.execute("INSERT INTO smoke_test (nombre) VALUES ('ok')")
        result = client.execute("SELECT nombre FROM smoke_test")
        rows = list(result.rows)
        assert len(rows) == 1
        assert rows[0][0] == "ok"
    finally:
        client.close()


def test_get_client_local_file_roundtrip(local_db_path):
    client = get_client(url=local_db_path)
    try:
        client.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, valor TEXT)")
        client.execute("INSERT INTO t (valor) VALUES (?)", ["hola"])
        result = client.execute("SELECT valor FROM t WHERE id = 1")
        rows = list(result.rows)
        assert len(rows) == 1
        assert rows[0][0] == "hola"
    finally:
        client.close()


def test_get_database_config_falls_back_to_local_file_without_env(monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    url, auth_token = get_database_config()

    assert url.startswith("file:")
    assert auth_token is None


def test_get_database_config_uses_env_vars_when_present(monkeypatch, tmp_path):
    db_file = tmp_path / "otra.db"
    monkeypatch.setenv("TURSO_DATABASE_URL", f"file:{db_file}")
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    url, auth_token = get_database_config()

    assert url == f"file:{db_file}"
    assert auth_token is None


def test_get_database_config_raises_if_remote_url_missing_token(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example-db.turso.io")
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    with pytest.raises(ConfigError):
        get_database_config()


def test_get_database_config_accepts_remote_url_with_token(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example-db.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "un-token-cualquiera")

    url, auth_token = get_database_config()

    assert url == "libsql://example-db.turso.io"
    assert auth_token == "un-token-cualquiera"
