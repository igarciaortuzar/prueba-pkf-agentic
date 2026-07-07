"""Entrypoint de la app Streamlit.

Alcance de este scaffold (item de cola "hosting-y-persistencia-turso", ver
`docs/adr/ADR-003-hosting-y-persistencia-turso.md"): hosting, conexión a la
base de datos (Turso/libSQL en producción, archivo local en dev) y el gate
de autenticación por contraseña compartida. El contenido real de la
aplicación (formularios de asistencia, esquema de tablas, motor de
validación RN-001/002/003) es responsabilidad del item de cola
"modelo-datos-motor-validacion" y todavía no está implementado — ver
`app/schema.py`.
"""
from __future__ import annotations

import streamlit as st

from app.auth import require_auth
from app.db import get_client

st.set_page_config(page_title="Libro de Clases Digital", layout="wide")


def main() -> None:
    if not require_auth():
        st.stop()

    st.title("Libro de Clases Digital")
    st.info(
        "Hosting y persistencia listos (Streamlit Community Cloud + Turso, "
        "ver ADR-003). El contenido funcional de la app (esquema de datos, "
        "formularios, motor de validación) todavía no está implementado — "
        "ver item de cola 'modelo-datos-motor-validacion'."
    )

    # Verificación mínima de que la conexión a la base de datos funciona.
    try:
        client = get_client()
        client.execute("SELECT 1")
        st.success("Conexión a la base de datos verificada.")
    except Exception as exc:  # pragma: no cover - solo diagnóstico visual
        st.error(f"No se pudo conectar a la base de datos: {exc}")


if __name__ == "__main__":
    main()
