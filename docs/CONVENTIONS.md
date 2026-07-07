# Convenciones de documentación

## Índice de docs/

| Archivo | Propósito |
|---|---|
| `CONVENTIONS.md` | Este archivo. Nombres, formatos, reglas de la documentación. |
| `business-rules.md` | Registro único de reglas de negocio (RN-xxx). |
| `adr/` | Decisiones de arquitectura, una por archivo. |
| `friction-log.md` | Bitácora de fricciones del framework (alimenta futuras versiones de PKF). |
| `examples/` | Patrones de referencia ilustrativos (ej. ADRs de ejemplo). No son reglas ni decisiones vigentes en este proyecto. |
| `testing/` | Protocolos de validación del framework mismo (no del proyecto de negocio). |

Cuando se agregue un documento nuevo a `docs/`, se registra en esta tabla.
Un documento que no está en el índice no existe para efectos del proyecto.

## Solo dos familias de IDs

PKF v0.1 usa identificadores únicamente donde la trazabilidad paga su costo:

- **RN-xxx** — reglas de negocio. Viven todas en `business-rules.md`.
- **ADR-xxx** — decisiones de arquitectura. Un archivo por decisión en `adr/`.

Todo lo demás (requerimientos, entidades, endpoints, tests) se referencia por
nombre descriptivo y por historial de Git. Si en la práctica eso genera fricción
real y repetida, se anota en `friction-log.md` antes de agregar una familia nueva.

## Formato de una regla de negocio

```markdown
### RN-XXX — Título corto de la regla

**Estado:** vigente | obsoleta (reemplazada por RN-xxx, fecha)
**Regla:** enunciado preciso, verificable, sin ambigüedad.
**Origen:** quién/qué la definió (contrato, cliente, ley, decisión interna).
**Historial:**
- 2026-07-03 — creada.
```

Los números no se reutilizan nunca, ni siquiera si la regla queda obsoleta.

## Nombres de archivo

- Minúsculas, guiones, sin tildes ni espacios: `flujo-de-aprobacion.md`.
- ADRs: `ADR-001-titulo-corto.md` (numeración correlativa, tres dígitos).

## Diagramas

Todo diagrama se escribe en Mermaid dentro del markdown. Si además se necesita
una imagen (para una presentación, por ejemplo), la imagen es un derivado:
la fuente de verdad es el bloque Mermaid.

## Marcar contenido obsoleto

Nunca borrar. Formato:

```markdown
> ⚠️ OBSOLETO desde 2026-07-03. Reemplazado por [lo que corresponda].
```

El contenido obsoleto puede moverse al final del documento, pero no eliminarse.
