"""Placeholder — esquema de datos del dominio.

INTENCIONALMENTE VACÍO. El esquema de tablas (articulos, cursos,
participantes, asistencias, sc_participantes_esperados) y el motor de
validación de las reglas de negocio RN-001/RN-002/RN-003 son
responsabilidad del item de cola "modelo-datos-motor-validacion"
(ver `specs/modelo-datos-motor-validacion.md` y
`docs/adr/ADR-004-modelo-datos-motor-validacion.md`), que se implementa en
una tarea separada.

Este módulo existe solo para dejar un punto de extensión explícito y
documentado: cuando se implemente ese item, el código de creación de
tablas y el motor de validación deberían vivir aquí (o en submódulos de
`app/`), reutilizando `app.db.get_client()` para la conexión.
"""
