# ADR-002 — Orquestar PKF con hooks y subagentes de Claude Code

**Fecha:** 2026-07-07
**Estado:** aceptada

## Contexto

`docs/friction-log.md` (entrada 2026-07-03) registró que PKF dependía de que
la IA leyera `AGENTS.md` por su cuenta y de que nadie editara por error
`docs/business-rules.md` o un ADR aceptado; detectar una condensación que
había perdido cláusulas de comportamiento solo fue posible revisando el diff
línea por línea, no confiando en un resumen. La solución candidata anotada
ahí era extender la regla de "mostrar diff antes de guardar" a más archivos
de alto impacto, pero PKF no tenía mecanismo para hacer cumplir eso —
dependía de disciplina, no de tooling.

## Decisión

Usar tres mecanismos nativos de Claude Code para que PKF se aplique solo,
sin depender de que el agente recuerde las reglas:

- Un hook `SessionStart` que inyecta `AGENTS.md` como contexto en cada sesión.
- Un hook `PreToolUse` (`protect_files.py`) que bloquea `Edit`/`Write` sobre
  `AGENTS.md`, `docs/business-rules.md` y ADRs ya aceptados
  (`docs/adr/ADR-\d{3}-*.md`), saliendo con código 2 — un bloqueo real, no
  una sugerencia.
- Un hook `PostToolUse` (`run_pkf_linter.sh`) que corre `tools/check_refs.py`
  tras cada edición.
- Cuatro subagentes con herramientas acotadas que forman un pipeline
  secuencial y no encadenado automáticamente: `pkf-spec` → `pkf-architect` →
  `pkf-implementer` → `pkf-auditor`, coordinados por `queue/_queue.json`.

Los ADRs en borrador se distinguen de los aceptados por **nombre de archivo**
(`docs/adr/DRAFT-<slug>.md` sin proteger, vs. `docs/adr/ADR-0XX-<slug>.md`
protegido) en vez de por carpeta, para no romper la numeración correlativa
existente ni el glob no-recursivo de `tools/check_refs.py`. Ver
`docs/orquestacion-claude-code.md` sección 4 para el detalle.

## Alternativas consideradas

- **Carpetas separadas `docs/adr/drafts/` y `docs/adr/accepted/`** —
  descartada: habría requerido mover `ADR-001` a una subcarpeta y parchear
  `tools/check_refs.py` para que busque ADRs recursivamente, tocando una
  convención y un linter ya en uso sin necesidad real.
- **Seguir dependiendo solo de `AGENTS.md` como texto** — descartada: es
  exactamente el problema que originó esta decisión (ver friction-log).
- **Bloquear también `Bash` en el hook de protección** — descartada por
  ahora: el pipeline actual asume que el `mv`/edición de promoción de un ADR
  lo hace un humano deliberadamente; se deja anotado como paso siguiente si
  se automatiza más el `pkf-implementer`.

## Consecuencias

Se gana: los guardrails de PKF pasan de ser texto que un agente podría
ignorar a comportamiento forzado por hooks, y hay un pipeline de roles con
límites explícitos de herramientas por rol. Se pierde/acepta: más piezas que
mantener (`.claude/hooks/`, `.claude/agents/`, `queue/`, `specs/`), y la
protección de `Edit`/`Write` no cubre `Bash` (un `mv` o `sed -i` la esquiva
por diseño, ya que se usa deliberadamente para la promoción humana de ADRs).
Riesgo vigilado: que `PROTECTED_PATTERNS` quede desactualizado si se agregan
archivos de alto impacto nuevos sin anotarlo en `docs/friction-log.md`.

## Referencias

- `docs/friction-log.md`, entrada 2026-07-03.
- `docs/orquestacion-claude-code.md`.
- ADR-001 (contexto de por qué existe PKF).
