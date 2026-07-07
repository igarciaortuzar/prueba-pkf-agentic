# ADR-001 — Adoptar PKF v0.1 como estructura del proyecto

**Fecha:** 2026-07-03
**Estado:** aceptada

## Contexto

Los proyectos anteriores dependían de contexto conversacional con la IA: cada sesión
nueva partía de cero o de memoria imperfecta. Se necesita que cualquier IA (y cualquier
persona) pueda incorporarse al proyecto leyendo archivos del repositorio, con
trazabilidad de reglas de negocio y decisiones técnicas, sin agregar mantenimiento
que una sola persona no pueda sostener.

## Decisión

Usar PKF v0.1: `AGENTS.md` como contrato de colaboración, `docs/` con convenciones
explícitas, reglas de negocio con ID (RN-xxx) en un registro único, decisiones como
ADRs inmutables, y un linter mínimo (`tools/check_refs.py`) que valida referencias.

## Alternativas consideradas

- **Framework completo desde el día uno** (capa de conocimiento en YAML, 11 familias
  de IDs, ciclo de vida de 10 etapas) — descartado: triplica las fuentes de verdad,
  depende de disciplina en vez de tooling, y el costo de mantención supera el valor
  para un equipo de una persona.
- **No usar framework** (repo ad-hoc) — descartado: es exactamente el problema que
  se quiere resolver; cada proyecto reinventa su organización.

## Consecuencias

Se gana: onboarding de IA en minutos, decisiones y reglas trazables, base común
reutilizable entre proyectos. Se pierde/acepta: cierta ceremonia en cambios
estructurales, y la obligación de correr el linter. Riesgo vigilado: que el framework
crezca por elegancia y no por fricción real; por eso existe `docs/friction-log.md`
y la regla de que toda pieza nueva debe nacer de una fricción documentada.

## Referencias

- Estándar AGENTS.md: https://agents.md
- Formato ADR de Michael Nygard (adaptado).
