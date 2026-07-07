"""Gate de autenticación por contraseña compartida a nivel de aplicación.

Decisión de arquitectura: ver `docs/adr/ADR-003-hosting-y-persistencia-turso.md`.
El acceso externo de las OTECs se protege con una contraseña compartida
(no cuentas individuales, no licenciamiento por usuario, no roles
granulares — eso está explícitamente fuera de alcance).

La contraseña esperada vive en `st.secrets["APP_PASSWORD"]` (ver
`.streamlit/secrets.toml.example`). Este módulo separa la lógica de
verificación (testeable sin navegador) de su uso dentro de la UI de
Streamlit (`require_auth()`, que sí depende de `st.session_state` /
widgets y no se ejercita directamente en tests unitarios).
"""
from __future__ import annotations

import os
from typing import Optional


class AuthConfigError(RuntimeError):
    """No hay contraseña configurada (falta APP_PASSWORD en secrets/entorno)."""


def _get_expected_password() -> Optional[str]:
    """Lee la contraseña esperada desde `st.secrets` (producción) o, como
    fallback, desde la variable de entorno `APP_PASSWORD` (dev/tests).
    """
    try:
        import streamlit as st

        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD")


def check_password(candidate: str, expected: Optional[str] = None) -> bool:
    """Compara `candidate` contra la contraseña esperada.

    Si no se pasa `expected` explícito, se resuelve vía
    `_get_expected_password()`. Lanza `AuthConfigError` si no hay ninguna
    contraseña configurada en ningún lado (evita el caso peligroso de
    "no hay secret configurado -> cualquier contraseña pasa").
    """
    if expected is None:
        expected = _get_expected_password()

    if not expected:
        raise AuthConfigError(
            "No hay APP_PASSWORD configurado en st.secrets ni en el entorno."
        )

    return candidate == expected


def require_auth() -> bool:
    """Gate de autenticación para usar dentro de `app.py`.

    Muestra un formulario de contraseña con `st.session_state` para no
    volver a pedirla en cada rerun de Streamlit dentro de la misma sesión
    del navegador. Devuelve True si el usuario ya está autenticado (o
    acaba de autenticarse en este rerun), False si debe seguir mostrando
    el formulario y detener el resto de la app.

    No testeado directamente con pytest (depende de `st.session_state` y
    widgets interactivos de Streamlit, que requieren un runtime de
    Streamlit real o `streamlit.testing.v1.AppTest`); la lógica de
    comparación de contraseña sí está cubierta vía `check_password()`.
    """
    import streamlit as st

    if st.session_state.get("authenticated", False):
        return True

    st.title("Acceso")
    password = st.text_input("Contraseña", type="password")
    submitted = st.button("Ingresar")

    if submitted:
        try:
            if check_password(password):
                st.session_state["authenticated"] = True
                return True
            st.error("Contraseña incorrecta.")
        except AuthConfigError as exc:
            st.error(f"Error de configuración: {exc}")

    return False
