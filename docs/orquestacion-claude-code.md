# Orquestación de PKF con Claude Code

> Ver `ADR-002` para la decisión y sus alternativas. Este documento es la guía
> operativa: cómo instalar y usar el pipeline.

Este mecanismo convierte PKF de "documentación que un agente debería seguir"
a "reglas que Claude Code aplica automáticamente", usando tres piezas reales
de Claude Code: **hooks**, **subagentes**, y un **archivo de cola**
(`queue/_queue.json`) para trackear items de trabajo entre sesiones.

## 1. Qué instala

```
.claude/settings.json                          # registra los hooks
.claude/hooks/session_start_inject_agents.sh    # inyecta AGENTS.md al iniciar sesión
.claude/hooks/protected_patterns.py             # lista compartida de rutas protegidas (ADR-006)
.claude/hooks/protect_files.py                  # bloquea Edit/Write sobre archivos protegidos
.claude/hooks/protect_bash_writes.py            # bloquea escrituras directas via Bash a archivos protegidos (ADR-006)
.claude/hooks/run_pkf_linter.sh                  # corre tools/check_refs.py tras cada edición
.claude/agents/pkf-spec.md                      # rol 1: escribe specs, nunca toca código
.claude/agents/pkf-architect.md                 # rol 2: valida contra business-rules + ADRs, deja un ADR en DRAFT
.claude/agents/pkf-implementer.md                # rol 3: implementa según spec + ADR aceptado
.claude/agents/pkf-auditor.md                    # rol 4: audita el diff línea por línea, nunca edita
queue/_queue.json                               # cola de items con status
specs/ejemplo-extender-guardrail-adr.md         # ejemplo del formato de spec
tools/add_business_rule.py                      # único camino sancionado para crear/obsoletar RN vía Bash (ADR-006)
```

Después de instalar, reinicia la sesión de Claude Code: los subagentes se
cargan al inicio de sesión, así que si editas los archivos de `.claude/agents/`
hay que reiniciar para que tome el cambio.

## 2. Qué resuelve cada pieza

| Problema | Solución |
|---|---|
| Depender de que el agente lea `AGENTS.md` por su cuenta | Hook `SessionStart` lo inyecta como contexto automáticamente en cada sesión |
| Un agente podría editar `docs/business-rules.md` o un ADR aceptado sin que nadie lo note | Hook `PreToolUse` bloquea esas rutas con código de salida 2 — el agente no puede proceder, ni siquiera en modo sin confirmaciones |
| El mismo hueco, pero vía `Bash` (heredoc, `sed -i`, `tee`, etc. directos a un archivo protegido, evitando `Edit`/`Write`) | Hook `PreToolUse` nuevo (`protect_bash_writes.py`, ADR-006) bloquea (código de salida 2) comandos de `Bash` que mencionen una ruta protegida junto a un token de escritura, con dos excepciones auditables: el `mv`/`git mv` de promoción de ADR, y la invocación de `tools/add_business_rule.py` |
| El linter de referencia (`tools/check_refs.py`) depende de que alguien se acuerde de correrlo | Hook `PostToolUse` lo corre automáticamente tras cada edición y fuerza a corregir si falla |
| La idea abierta en `docs/friction-log.md` (2026-07-03): extender la regla de diff-antes-de-guardar a más archivos protegidos | `PROTECTED_PATTERNS` vive en `protected_patterns.py`, módulo compartido entre `protect_files.py` y `protect_bash_writes.py` — agregar un archivo nuevo es una línea, y ambos hooks quedan sincronizados |
| Crear/obsoletar una RN sin depender de que un hook heurístico "deje pasar por accidente" un heredoc de `Bash` | `tools/add_business_rule.py` (subcomandos `create`/`deprecate`) es el único camino sancionado, con validación de formato y numeración antes de escribir |
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

## 5. Protección de `Bash` contra escrituras directas a archivos protegidos (ADR-006)

Ver `ADR-006` (`docs/adr/ADR-006-hook-proteccion-bash.md`) para la decisión
completa y su razonamiento ("Bloqueo real con excepciones auditables"). Esta
sección es la guía operativa, con el mismo nivel de detalle que la sección 4.

**El problema que cierra:** `protect_files.py` (sección 2) solo intercepta
`Edit`/`Write`. Nada impedía, hasta ADR-006, que `Bash` escribiera contenido
nuevo directamente en `AGENTS.md`, `docs/business-rules.md` o un ADR ya
aceptado vía heredoc, `sed -i`, `tee`, etc. — evitando por completo ese
guardrail (ver `docs/friction-log.md`, entrada 2026-07-07).

**Cómo funciona `protect_bash_writes.py`:** hook `PreToolUse` nuevo, registrado
en `.claude/settings.json` con `matcher: "Bash"`, que se ejecuta antes de cada
invocación de `Bash` y decide, en orden:

1. **Short-circuit:** si el comando no menciona textualmente ninguna de las
   rutas de `PROTECTED_PATTERNS` (módulo compartido `protected_patterns.py`,
   usado también por `protect_files.py` para no duplicar la lista), se
   permite de inmediato sin más análisis. Cubre la inmensa mayoría del uso
   normal de `Bash` (`pytest`, `git status`, `python tools/check_refs.py`,
   etc.) sin riesgo de falso positivo.
2. **Excepción 1 — promoción de ADR:** un `mv`/`git mv` de dos argumentos
   exactos, sin encadenar con nada más (`;`, `&&`, `||`, `|`, backticks,
   `$(...)`), donde el origen es `DRAFT-<slug>.md`, el destino es
   `ADR-0XX-<slug>.md`, y el `<slug>` es idéntico en ambos — se permite. Esto
   es lo que mantiene sin fricción el flujo de la sección 4.
3. **Excepción 2 — script sancionado:** una invocación (también sin
   encadenar) de `python tools/add_business_rule.py ...` se permite; la
   validación de fondo la hace el script mismo, no el hook.
4. **Caso general:** si el comando menciona una ruta protegida, no calzó
   ninguna excepción, y además contiene un token que "parece" escritura
   (`>`, `>>`, `sed -i`, `tee`, `cp `, `install `, `rsync`, `dd `, `perl -i`,
   `truncate`, o un `mv`/`git mv` que no calzó exactamente la excepción 1),
   se bloquea con código de salida 2. Si solo hay mención sin token de
   escritura (`cat docs/business-rules.md`, `git diff AGENTS.md`), se
   permite — es lectura.

**Límites honestos (no es un guardrail perfecto):** es una heurística de
texto sobre el string del comando, no una señal perfecta como el `file_path`
que sí entrega `Edit`/`Write`. Hay falsos negativos conocidos (ofuscación de
ruta vía variables o `$(...)`, herramientas de escritura no listadas) y
falsos positivos acotados (un comando de solo lectura que mencione un
archivo protegido junto a un token de escritura dirigido a *otro* archivo,
p. ej. `cat docs/business-rules.md | tee /tmp/copia.md`). Ver ADR-006,
sección "Consecuencias", para el detalle completo. No cubre comandos
destructivos (`rm -rf`, `git push --force`) — eso sigue siendo una idea
separada, no incluida (ver sección 6).

**`tools/add_business_rule.py`:** único camino sancionado para crear u
obsoletar una RN vía `Bash` dentro de una sesión de Claude Code, invocado con
instrucción explícita del dueño del proyecto (P2 de `AGENTS.md`). Dos
subcomandos:

- `create --numero NNN --titulo "..." --regla "..." --origen "..." [--fecha AAAA-MM-DD]`
  — valida que `docs/business-rules.md` exista y tenga la línea `**Próximo
  número disponible:** NNN`, que `--numero` coincida exactamente con ese
  valor (si no, aborta e informa el número real vigente, sin escribir nada),
  y que `--titulo`/`--regla`/`--origen` no estén vacíos, no tengan saltos de
  línea, y no contengan `### RN-` ni `**Estado:**` (evita inyectar un bloque
  Markdown completo o alterar el `Estado` de otra RN desde un campo de
  texto). Si todo pasa, inserta el bloque nuevo en el formato de
  `docs/CONVENTIONS.md` antes del comentario `<!-- PLANTILLA ... -->`,
  actualiza `**Próximo número disponible:**`, y escribe de forma atómica
  (archivo temporal + `os.replace`).
- `deprecate --numero NNN --reemplazada-por RN-NNN [--fecha AAAA-MM-DD]` —
  valida que la RN exista y su `Estado:` actual sea `vigente` (no se puede
  obsoletar dos veces); cambia únicamente esa línea a `**Estado:** obsoleta
  (reemplazada por RN-NNN, fecha)` y agrega una línea a su `Historial:`. El
  enunciado original de la regla y el resto del archivo no se tocan (P5 de
  `AGENTS.md` — nunca se borra historia).

Cualquier validación que falle termina el script con código distinto de
cero, un mensaje claro en `stderr`, y **sin tocar el archivo**.

**Lo que sigue manual, a propósito:** la promoción de ADR (sección 4) no se
automatiza con un `tools/promote_adr.py` — sigue siendo un gesto humano
deliberado (`mv`/`git mv` + edición manual de `Estado:`), decisión explícita
formalizada en ADR-006. Tampoco se verifica *quién* invoca
`tools/add_business_rule.py` ni si hubo, en efecto, instrucción explícita del
dueño — eso sigue siendo responsabilidad de la sesión de Claude Code, igual
que con cualquier edición de `business-rules.md` hoy.

## 6. Siguientes pasos sugeridos (no incluidos aún)

- ~~Agregar un hook `PreToolUse` sobre `Bash` para bloquear escrituras
  directas a archivos protegidos~~ — implementado 2026-07-07, ver sección 5
  y ADR-006. Sigue pendiente, y explícitamente fuera del alcance de ADR-006,
  bloquear comandos destructivos de `Bash` (`rm -rf`, `git push --force`,
  etc.) si se da más autonomía al `pkf-implementer`.
- Si más adelante se necesita paralelismo real entre varios items de la cola
  al mismo tiempo, usar git worktrees por slug en vez de una sola sesión
  secuencial.
