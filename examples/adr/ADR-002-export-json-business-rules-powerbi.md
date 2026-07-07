# ADR-002 — Exportar business-rules.md a JSON para consumo desde Power BI

**Fecha:** 2026-07-03
**Estado:** ejemplo ilustrativo (no vigente en este proyecto)

## Contexto

Power BI necesita mostrar las reglas de negocio (RN-xxx) en un dashboard, pero
`Web.Contents` no puede parsear Markdown directamente. Necesitamos exponer las
reglas en un formato consumible sin comprometer el principio de PKF de mantener
la fuente de verdad simple, versionada en texto plano y sin infraestructura
adicional que un equipo de una persona no pueda sostener (ver ADR-001).

## Decisión

Generar un export derivado en JSON (`docs/business-rules.json`) mediante un
script (`tools/export_business_rules.py`) que parsea `docs/business-rules.md`.
Power BI lee ese JSON vía `Web.Contents`, apuntando al archivo local o a la URL
RAW de GitHub. El Markdown sigue siendo la única fuente de verdad; el JSON es
un artefacto generado, nunca se edita a mano, y se regenera corriendo el script
antes de cada commit que toque `business-rules.md`.

## Alternativas consideradas

- **Endpoint REST con FastAPI** — descartado: implica levantar y mantener un
  servicio (hosting, uptime, autenticación, monitoreo) solo para exponer un
  puñado de reglas de texto. Desproporcionado para el volumen actual y
  contrario a la premisa de ADR-001 de minimizar infraestructura.
- **Mover el registro a Excel o SQLite** — descartado en una decisión previa:
  el Markdown en git ya resuelve persistencia, historial y diffabilidad sin
  dependencias nuevas; no había fricción real que lo justificara.

## Consecuencias

Se gana: Power BI consume las reglas sin infraestructura nueva ni servidor que
mantener; el export es trivial de regenerar y no introduce dependencias más
allá de la librería estándar de Python. Se pierde/acepta: el JSON puede quedar
desactualizado si alguien edita `business-rules.md` y olvida correr el script
antes de comitear (mismo riesgo ya aceptado con `tools/check_refs.py`). Si el
volumen de reglas crece mucho o se necesita refresco en tiempo real, esta
decisión debería revisarse.

## Referencias

- ADR-001 (principio de minimalismo del framework).
- `docs/friction-log.md` — entrada 2026-07-03.
- `tools/export_business_rules.py`
