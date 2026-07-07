# Orquestación de PKF con Claude Code

> Ver `ADR-002` para la decisión y sus alternativas. Este documento es la guía
> operativa: cómo instalar y usar el pipeline.

Este mecanismo convierte PKF de "documentación que un agente debería seguir"
a "reglas que Claude Code aplica automáticamente", usando tres piezas reales
de Claude Code: **hooks**, **subagentes**, y un **archivo de cola**
(`queue/_queue.json`) para trackear items de trabajo entre sesiones.

## 1. Qué instala

```
.claude/settings.json                          # registra los 3 hooks
.claude/hooks/session_start_inject_agents.sh    # inyecta AGENTS.md al iniciar sesión
.claude/hooks/protect_files.py                  # bloquea Edit/Write sobre archivos protegidos
.claude/hooks/run_pkf_linter.sh                  # corre tools/check_refs.py tras cada edición
.claude/agents/pkf-spec.md                      # rol 1: escribe specs, nunca toca código
.claude/agents/pkf-architect.md                 # rol 2: valida contra business-rules + ADRs, deja un ADR en DRAFT
.claude/agents/pkf-implementer.md                # rol 3: implementa según spec + ADR aceptado
.claude/agents/pkf-auditor.md                    # rol 4: audita el diff línea por línea, nunca edita
queue/_queue.json                               # cola de items con status
specs/ejemplo-extender-guardrail-adr.md         # ejemplo del formato de spec
```

Después de instalar, reinicia la sesión de Claude Code: los subagentes se
cargan al inicio de sesión, así que si editas los archivos de `.claude/agents/`
hay que reiniciar para que tome el cambio.

## 2. Qué resuelve cada pieza

| Problema | Solución |
|---|---|
| Depender de que el agente lea `AGENTS.md` por su cuenta | Hook `SessionStart` lo inyecta como contexto automáticamente en cada sesión |
| Un agente podría editar `docs/business-rules.md` o un ADR aceptado sin que nadie lo note | Hook `PreToolUse` bloquea esas rutas con código de salida 2 — el agente no puede proceder, ni siquiera en modo sin confirmaciones |
| El linter de referencia (`tools/check_refs.py`) depende de que alguien se acuerde de correrlo | Hook `PostToolUse` lo corre automáticamente tras cada edición y fuerza a corregir si falla |
| La idea abierta en `docs/friction-log.md` (2026-07-03): extender la regla de diff-antes-de-guardar a más archivos protegidos | `PROTECTED_PATTERNS` en `protect_files.py` es una lista — agregar un archivo nuevo es una línea |
| Necesitas un pipeline de trabajo, no solo un agente genérico | 4 subagentes con roles y herramientas acotadas: `pkf-spec` → `pkf-architect` → `pkf-implementer` → `pkf-auditor` |

## 3. Cómo se ve un flujo real

```
Tu: "Necesito extender el guardrail de diff-antes-de-guardar a más archivos"

1. Usa el subagente pkf-spec sobre esto.
   -> escribe specs/extender-guardrail.md
   -> status: READY_FOR_ARCH

2. [Revisas el spec tú mismo -- es corto, vale la pena leerlo]

3. Usa el subagente pkf-architect sobre 'extender-guardrail'.
   -> escribe docs/adr/DRAFT-extender-guardrail.md (Estado: propuesta)
   -> status: READY_FOR_BUILD

4. [Revisas la propuesta de ADR. Si estás de acuerdo:]
   - edita Estado: propuesta -> Estado: aceptada
   - mv docs/adr/DRAFT-extender-guardrail.md docs/adr/ADR-0XX-extender-guardrail.md
     (siguiente número correlativo)
   (ese renombrado es la aprobación humana -- a partir de aquí el hook protege el archivo)

5. Usa el subagente pkf-implementer sobre 'extender-guardrail'.
   -> implementa, corre tests
   -> status: READY_FOR_REVIEW

6. Usa el subagente pkf-auditor sobre 'extender-guardrail'.
   -> revisa el diff línea por línea, corre tools/check_refs.py, dictamina
   -> status: DONE o NEEDS_FIXES
```

Nada de esto se auto-invoca en cadena: cada subagente termina con una sola
línea sugiriendo el siguiente paso, y tú decides si seguir. Es el mismo
principio que ya rige `AGENTS.md` — el framework depende de auditoría humana
del diff, no de infalibilidad de la IA.

## 4. Por qué `DRAFT-<slug>.md` y no dos carpetas

Este proyecto ya distingue "propuesta" de "aceptada" con el campo
**Estado:** dentro del propio archivo ADR (ver `docs/adr/TEMPLATE.md`), y
`tools/check_refs.py` busca ADRs directamente en `docs/adr/` sin recursividad.
Meter una propuesta bajo un nombre `ADR-0XX-...` antes de tiempo rompería esa
numeración correlativa y confundiría al linter.

Por eso el `pkf-architect` escribe su propuesta como `docs/adr/DRAFT-<slug>.md`
(no matchea ni el patrón protegido ni el glob `ADR-*.md` del linter).
Promover un ADR es un gesto humano deliberado en dos pasos, dentro del mismo
archivo primero y como archivo después:

1. Cambiar `Estado: propuesta` -> `Estado: aceptada` (mientras el archivo
   todavía se llama `DRAFT-<slug>.md`, sin protección).
2. Renombrar el archivo a `docs/adr/ADR-0XX-<slug>.md`, asignando el próximo
   número correlativo. Ese renombrado es lo que activa la protección del
   hook — no algo que un agente decide por su cuenta.

Esto evita tener que resolver "qué subagente está pidiendo este cambio"
dentro del hook, que no es información confiable de tener en el JSON del
evento, y no requiere tocar `tools/check_refs.py` ni la convención de
numeración ya en uso.

## 5. Siguientes pasos sugeridos (no incluidos aún)

- Agregar un hook `PreToolUse` sobre `Bash` para bloquear comandos
  destructivos (`rm -rf`, `git push --force`, etc.) si se da más autonomía
  al `pkf-implementer` — hoy el hook de protección solo mira `Edit`/`Write`,
  así que un `mv` o `sed -i` vía `Bash` no está bloqueado por diseño (se
  asume que ese `mv` es precisamente el gesto humano de promoción; si se
  automatiza más adelante, revisar este supuesto).
- Si más adelante se necesita paralelismo real entre varios items de la cola
  al mismo tiempo, usar git worktrees por slug en vez de una sola sesión
  secuencial.
