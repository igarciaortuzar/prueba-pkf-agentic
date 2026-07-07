# Bitácora de fricciones

> Aquí se anota toda fricción real encontrada al trabajar con el framework:
> algo que la IA no encontró, un rastro que se perdió, una convención que estorbó.
> **Regla de oro de PKF:** ninguna pieza nueva entra al framework si no nace
> de una entrada en esta bitácora. El framework crece por extracción, no por diseño.

## Formato

```markdown
### 2026-07-15 — Título corto de la fricción
**Proyecto:** en cuál ocurrió.
**Qué pasó:** descripción concreta del dolor.
**Frecuencia:** primera vez | recurrente (n veces).
**Solución candidata:** (opcional, solo si es evidente).
```

Una fricción que ocurre una sola vez probablemente no justifica cambios.
Una que se repite en dos proyectos distintos, casi seguro que sí.

---

### 2026-07-03 — AGENTS.md no especifica cómo proceder ante ediciones de alto impacto
**Proyecto:** PKF v0.1.
**Qué pasó:** el Test 8 mostró que la sección 5 decía qué archivos requieren
instrucción explícita para modificarse, pero no cómo proceder una vez que se
tiene esa instrucción. Un pedido legítimo y explícito ("simplifica AGENTS.md")
se ejecutó sobrescribiendo el archivo directo, sin mostrar el cambio antes de
guardarlo — y la condensación resultante perdió cláusulas de comportamiento
real en P1, P2, P4 y P6 sin que fuera evidente hasta revisar el diff línea
por línea.
**Frecuencia:** primera vez.
**Solución candidata:** agregar a la sección 5 la regla de mostrar diff antes
de guardar cambios a AGENTS.md (ya aplicada).

---

### 2026-07-03 — El framework depende de que alguien audite el diff, no de que la IA no se equivoque
**Proyecto:** PKF v0.1.
**Qué pasó:** en el Test 3, el Test 8 y la revisión de la condensación de
AGENTS.md, Claude Code produjo resultados razonables pero no exactamente
correctos ante instrucciones vagas o subespecificadas; detectarlo requirió
comparar línea por línea contra la fuente original en cada caso.
**Frecuencia:** recurrente (3 veces en esta sesión de validación).
**Solución candidata:** evaluar extender la regla de "mostrar diff antes de
guardar" (agregada en sección 5 para AGENTS.md) a otros archivos de alto
impacto — business-rules.md, ADRs aceptados.

> Implementado 2026-07-07 vía hooks de Claude Code (`PreToolUse` bloquea
> `Edit`/`Write` sobre esos archivos con código de salida 2). Ver ADR-002 y
> `docs/orquestacion-claude-code.md`.

---

### 2026-07-07 — `pkf-spec` no tenía permiso `Write` pese a que su rol lo exige
**Proyecto:** Sistema de Validación Preventiva y Libro de Clases Digital (pipeline PKF con Claude Code).
**Qué pasó:** el subagente `pkf-spec` (heredado del kit de instalación) tenía
`tools: Read, Grep, Glob` — sin `Write` — pese a que sus instrucciones de rol
dicen explícitamente "Escribe (o actualiza) `specs/<slug>.md`" y "Actualiza
`queue/_queue.json`". La primera vez que se invocó para un item real, no
pudo persistir nada: devolvió el contenido completo en su respuesta para
que el orquestador (sesión principal) lo grabara manualmente. Se corrigió
agregando `Write` a su lista de `tools`.
**Frecuencia:** primera vez (detectado al primer uso real del subagente).
**Solución candidata:** al instalar o modificar cualquier subagente,
verificar que su lista de `tools` sea consistente con las acciones que sus
instrucciones de rol le piden ejecutar — ya aplicado a `pkf-spec`, vale la
pena revisar `pkf-architect`, `pkf-implementer` y `pkf-auditor` si se les
agregan responsabilidades nuevas en el futuro.

---

### 2026-07-07 — La protección de archivos (hook `PreToolUse`) no cubre `Bash`
**Proyecto:** Sistema de Validación Preventiva y Libro de Clases Digital (pipeline PKF con Claude Code).
**Qué pasó:** `protect_files.py` bloquea `Edit`/`Write` sobre `AGENTS.md`,
`docs/business-rules.md` y ADRs aceptados, pero no intercepta la
herramienta `Bash`. ADR-002 ya anotaba esto como decisión de diseño para
permitir el `mv` humano de promoción de ADR — pero en esta sesión se usó el
mismo camino para escribir contenido nuevo directamente en
`docs/business-rules.md` (crear RN-001/RN-002/RN-003) vía un heredoc de
Bash, un caso más amplio que el originalmente previsto. En la práctica, la
única barrera contra que el propio orquestador (o un subagente con acceso a
`Bash`) escriba en un archivo "protegido" es que decida seguir la
instrucción de mostrar el diff antes de guardar — no hay bloqueo técnico
real para ese camino.
**Frecuencia:** dos veces en esta sesión (promoción de ADR-003 y ADR-004
vía `git mv`, y creación de RN-001/002/003 vía heredoc).
**Solución candidata:** evaluar si vale la pena que `protect_files.py` (o un
hook `PreToolUse` nuevo sobre `Bash`) intente detectar comandos que escriban
directamente sobre rutas protegidas, aceptando que una heurística sobre
texto de comando nunca será tan confiable como interceptar por herramienta.
Alternativa más simple: dejarlo como está y confiar en la disciplina de
"mostrar diff antes de guardar" — pero eso depende de que la IA lo recuerde,
no de un guardrail duro, que es justamente el problema que motivó crear los
hooks en primer lugar (ver ADR-002).

> Implementado 2026-07-07 vía ADR-006 (`docs/adr/ADR-006-hook-proteccion-bash.md`):
> hook `PreToolUse` nuevo `.claude/hooks/protect_bash_writes.py` (mecanismo
> "Bloqueo real con excepciones auditables") bloquea con código de salida 2
> los comandos de `Bash` que escriban directamente sobre `PROTECTED_PATTERNS`
> (módulo compartido `protected_patterns.py`), con dos excepciones auditables:
> el `mv`/`git mv` exacto de promoción de ADR, y la invocación del script
> sancionado `tools/add_business_rule.py` (subcomandos `create`/`deprecate`)
> como único camino legítimo para crear/obsoletar RN vía `Bash`. Ver
> `docs/orquestacion-claude-code.md`, sección 5.

---

### 2026-07-07 — El pipeline secuencial se sintió lento en la práctica
**Proyecto:** Sistema de Validación Preventiva y Libro de Clases Digital (pipeline PKF con Claude Code).
**Qué pasó:** el dueño del proyecto notó que el ritmo de trabajo (spec →
architect → aprobación humana → implementer → auditor, un item de la cola a
la vez) se sentía lento, y preguntó dos veces si los subagentes podían
correr en paralelo. La respuesta es parcial: dentro de un mismo item los 4
roles tienen dependencias reales secuenciales (no paraleliza), pero entre
items independientes de la cola sí sería posible, usando git worktrees por
slug — mecanismo que ADR-002 ya anotaba como "siguiente paso, no incluido
aún". Esta sesión confirma que es una fricción real sentida al trabajar, no
solo un riesgo anticipado en el papel.
**Frecuencia:** primera vez verbalizada.
**Solución candidata:** implementar el mecanismo de git worktrees por slug
ya anotado en ADR-002 / `docs/orquestacion-claude-code.md`, cuando haya al
menos 2-3 items de la cola simultáneamente independientes entre sí que lo
justifiquen.

---

### 2026-07-07 — La captura de fricciones depende de que el dueño del proyecto se acuerde de preguntar, no ocurre por iniciativa propia
**Proyecto:** Sistema de Validación Preventiva y Libro de Clases Digital (pipeline PKF con Claude Code).
**Qué pasó:** durante toda esta sesión (instalación del kit, specs, ADRs,
RN, implementación del scaffold) ninguna fricción se registró en este
archivo por iniciativa de la IA. Las tres entradas anteriores del
2026-07-07 solo existen porque el dueño del proyecto preguntó
explícitamente, al final de la sesión, "¿encontraste alguna fricción?". Si
no hubiera preguntado, esas fricciones — incluyendo un bug real de
permisos en `pkf-spec` — se habrían perdido al cerrar la sesión. Esto
contradice directamente el principio fundacional de PKF ("el framework
crece por extracción, ver friction-log.md") si la extracción misma depende
de que un humano se acuerde de pedirla en vez de ser parte natural del
flujo de trabajo.
**Frecuencia:** primera vez verbalizada, pero aplica retroactivamente a
toda la sesión: ni la sesión principal ni ningún subagente propuso una
entrada de friction-log sin que se le preguntara.
**Solución candidata:** ninguna implementada todavía — son ideas abiertas,
no una decisión:
- Agregar un paso explícito en `AGENTS.md` (sección 6, o una nueva) que
  pida proponer candidatas a friction-log antes de cerrar cualquier tarea
  no trivial, en vez de esperar a que se pregunte.
- Un hook `Stop` de Claude Code (análogo al `SessionStart` que ya inyecta
  `AGENTS.md`) que recuerde, al final de cada sesión, revisar si hubo
  fricciones sin registrar.
- Aceptar que sea un hábito humano deliberado — documentado
  explícitamente en vez de dejarlo implícito, para que no dependa de la
  memoria de una sola persona.

Nota: implementar cualquiera de estas opciones (en particular un hook
nuevo) sería un cambio estructural (P3 de `AGENTS.md`: nueva integración)
y requeriría su propio spec/ADR antes de tocar código — esta entrada deja
la fricción documentada, no toma la decisión.

> Implementado 2026-07-07 vía ADR-005
> (`docs/adr/ADR-005-captura-automatica-fricciones.md`): combinación de
> Opción 1 (paso explícito nuevo, sección 7 de `AGENTS.md`, que exige
> proponer candidatas a friction-log antes de cerrar tareas Normal o
> Estructural, y prohíbe escribir una entrada nueva sin anunciarla antes al
> dueño del proyecto) + Opción 2 acotada (hook `Stop` nuevo
> `.claude/hooks/stop_friction_reminder.py`, que no dispara en cada turno,
> solo cuando la sesión editó `specs/`, un `DRAFT-*.md` de ADR o
> `docs/business-rules.md`). Ver `docs/orquestacion-claude-code.md`,
> sección 6. La señal de `transcript_path` se verificó viable en la
> práctica (no fue necesario recurrir a la alternativa de respaldo `git
> diff --name-only` anotada en ADR-005). **Pendiente:** la sección 7 de
> `AGENTS.md` propuesta en ADR-005 todavía no fue aplicada — requiere
> revisión y aprobación explícita del dueño del proyecto antes de escribirse
> (P2 y sección 5 de `AGENTS.md`); el hook `Stop` ya está activo, pero el
> texto que le da contenido accionable al recordatorio aún no vive en
> `AGENTS.md`.
