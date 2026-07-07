"""Tests del gate de autenticación por contraseña compartida (`app/auth.py`).

Solo se testea `check_password()` (lógica pura, sin dependencia de
`st.session_state` ni de widgets). `require_auth()` depende del runtime de
Streamlit (session_state, formularios interactivos) y no se ejercita aquí
directamente — ver su docstring.
"""
from __future__ import annotations

import pytest

from app.auth import AuthConfigError, check_password


def test_check_password_with_explicit_expected_matches():
    assert check_password("secreta", expected="secreta") is True


def test_check_password_with_explicit_expected_mismatches():
    assert check_password("incorrecta", expected="secreta") is False


def test_check_password_uses_env_var_when_no_explicit_expected(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "clave-del-entorno")

    assert check_password("clave-del-entorno") is True
    assert check_password("otra-cosa") is False


def test_check_password_raises_if_nothing_configured(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)

    with pytest.raises(AuthConfigError):
        check_password("cualquier-cosa")
