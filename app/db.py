"""Capa de conexión a la base de datos.

Decisión de arquitectura: ver `docs/adr/ADR-003-hosting-y-persistencia-turso.md`
(Turso/libSQL como motor de base de datos, hosteado junto con la app en
Streamlit Community Cloud; credenciales vía `st.secrets`).

En producción la conexión apunta a Turso usando `TURSO_DATABASE_URL` +
`TURSO_AUTH_TOKEN`, leídos de `st.secrets` (ver `.streamlit/secrets.toml.example`).
Para desarrollo local y para que los tests corran sin credenciales reales de
Turso, esta misma capa acepta también una URL de archivo libSQL/SQLite local
(`file:...`) — libsql-client soporta ambos esquemas con la misma API. Esto no
contradice ADR-003: ese ADR decide la persistencia de *producción*, no impide
usar un archivo local para dev/tests.

Fuera de alcance de este módulo (ver item de cola
"modelo-datos-motor-validacion" / ADR-004): el esquema de tablas del dominio
(articulos, cursos, participantes, asistencias, sc_participantes_esperados)
y el motor de validación de las reglas de negocio RN-001/RN-002/RN-003. Ese
esquema vive en `app/schema.py` (placeholder documentado, sin implementar
todavía).
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import libsql_client

# URL de archivo local usada cuando no hay configuración de Turso disponible
# (desarrollo y tests). Relativa al directorio de trabajo del proceso.
DEFAULT_LOCAL_DB_PATH = "file:local.db"

# Esquemas de URL que corresponden a un servidor remoto de Turso/libSQL (y
# por lo tanto requieren auth_token). "file:" es local y no lo requiere.
_REMOTE_SCHEMES = ("libsql://", "https://", "http://", "wss://", "ws://")


class ConfigError(RuntimeError):
    """La configuración de conexión (secrets/entorno) es inválida o falta."""


def _get_secret(key: str) -> Optional[str]:
    """Busca `key` primero en `st.secrets` (producción / Streamlit Cloud) y
    si no está disponible, en variables de entorno (fallback para scripts y
    tests que corren fuera del runtime de Streamlit).

    Devuelve None si la clave no está definida en ningún lado. Nunca
    propaga la excepción de `st.secrets` cuando no existe `secrets.toml`
    (caso normal en desarrollo local / CI): eso simplemente significa "no
    hay secreto disponible por esta vía", no un error.
    """
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key)


def get_database_config() -> Tuple[str, Optional[str]]:
    """Resuelve (url, auth_token) para conectar a la base de datos.

    - Producción: usa `TURSO_DATABASE_URL` (ej. "libsql://<db>.turso.io") y
      `TURSO_AUTH_TOKEN" desde `st.secrets` (ver ADR-003).
    - Desarrollo / tests: si `TURSO_DATABASE_URL` no está definido, cae a un
      archivo libSQL local (`DEFAULT_LOCAL_DB_PATH`), sin auth token.

    Lanza `ConfigError` si la URL apunta a un servidor remoto pero falta el
    auth token (evita conexiones a medio configurar en producción).
    """
    url = _get_secret("TURSO_DATABASE_URL")
    auth_token = _get_secret("TURSO_AUTH_TOKEN")

    if not url:
        url = DEFAULT_LOCAL_DB_PATH

    if url.startswith(_REMOTE_SCHEMES) and not auth_token:
        raise ConfigError(
            "TURSO_DATABASE_URL apunta a un servidor remoto pero falta "
            "TURSO_AUTH_TOKEN en st.secrets (o en el entorno)."
        )

    return url, auth_token


def get_client(
    url: Optional[str] = None, auth_token: Optional[str] = None
) -> libsql_client.ClientSync:
    """Crea un cliente síncrono de libSQL.

    Si no se pasan `url`/`auth_token` explícitos, se resuelven vía
    `get_database_config()` (secrets de Streamlit o variables de entorno,
    con fallback a archivo local para dev/tests). Pensado para usarse tanto
    desde la app (`app.py`) como desde tests, pasando una URL de archivo
    temporal explícita en este último caso.
    """
    if url is None:
        url, auth_token = get_database_config()

    kwargs = {}
    if auth_token:
        kwargs["auth_token"] = auth_token

    return libsql_client.create_client_sync(url, **kwargs)
