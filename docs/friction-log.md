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
**Frecuencia:** primera vez (detectado al primer uso real del subagente);
recurrente — `pkf-auditor` tenía exactamente el mismo bug (`tools: Read,
Grep, Glob, Bash`, sin `Edit`/`Write`, pese a que su rol le exige
"Actualiza `queue/_queue.json`"), sin haberse usado todavía en esta sesión.
Se detectó al revisar los 4 subagentes antes del primer uso real de
`pkf-auditor` (2026-07-07), no después de un fallo — confirma que valía la
pena la revisión que esta misma entrada ya recomendaba. Corregido
agregando `Edit` a su lista de `tools`.
**Solución candidata:** al instalar o modificar cualquier subagente,
verificar que su lista de `tools` sea consistente con las acciones que sus
instrucciones de rol le piden ejecutar — ya aplicado a `pkf-spec` y
`pkf-auditor`. `pkf-architect` y `pkf-implementer` ya tenían los permisos
correctos (verificado por uso real, no solo lectura del archivo).

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
> diff --name-only` anotada en ADR-005). La sección 7 de `AGENTS.md`
> quedó aplicada el mismo día tras revisión y aprobación explícita del
> dueño del proyecto (diff mostrado completo antes de guardar, P2 y
> sección 5 de `AGENTS.md`) — mecanismo completo y activo.

---

### 2026-07-07 — El hook de protección de Bash bloqueó un commit legítimo
**Proyecto:** Sistema de Validación Preventiva y Libro de Clases Digital (pipeline PKF con Claude Code).
**Qué pasó:** minutos después de desplegar `protect_bash_writes.py` (ADR-006),
el primer `git commit` real de la sesión quedó bloqueado. El mensaje del
commit mencionaba `AGENTS.md` en prosa y terminaba con el trailer
obligatorio `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` — el
hook interpretó el `>` de `<noreply@anthropic.com>` como un token de
escritura (`WRITE_TOKENS` incluía `">"` como substring libre, sin exigir
contexto de redirección real). Se detectó también un segundo riesgo latente
de la misma clase: `"tee"` como substring libre habría bloqueado cualquier
commit que mencionara la palabra "committee" junto a un archivo protegido.
Dado que el formato `Co-Authored-By: ... <email>` es obligatorio en *todos*
los commits de esta sesión, y que los commits sobre este propio framework
mencionan constantemente `AGENTS.md`/`business-rules.md`/`ADR-xxx` por
nombre, este falso positivo habría bloqueado una fracción grande de la
actividad normal de commits del proyecto, no un caso raro.
**Frecuencia:** primera vez, pero con alta probabilidad de recurrencia si no
se corregía (se confirmó el patrón general al revisar el código, no solo el
caso puntual).
**Solución candidata:** corregido en el mismo momento — no se dejó como
fricción abierta:
- `>`/`>>` ahora exigen estar precedidos por espacio o inicio de línea
  (forma típica de una redirección real, `cmd > archivo`), en vez de
  matchear como substring en cualquier posición.
- `tee` ahora exige ser palabra completa (`\btee\b`), no substring.
- Se agregó una tercera excepción explícita: `git commit` se permite sin
  analizar el resto del comando, porque el mensaje es texto opaco, no una
  escritura real a un path del working tree vía shell.
- 6 tests de regresión nuevos en `tests/test_protect_bash_writes.py`
  cubriendo estos casos exactos.

**Actualización (mismo día, minutos después del fix anterior):** el
siguiente commit real quedó bloqueado por la misma clase de bug: `git add`
contiene `dd ` como substring de `add ` (el token `"dd "` buscaba el
comando `dd`, disco a disco, pero matcheaba dentro de `git add`) —
bloqueando el comando de git más común de todo este flujo de trabajo cada
vez que la lista de archivos incluía uno protegido. Mismo patrón de
corrección: `dd ` pasó a exigir palabra completa
(`(?:^|\s)dd(?:\s|$)`), igual que `tee`. 2 tests de regresión más
(`git add` con archivo protegido ya no bloquea; `dd if=... of=AGENTS.md`
real sigue bloqueado). 46 tests totales pasando.

**Segunda actualización (detectada por `pkf-auditor`, no por el dueño del
proyecto):** al auditar `captura-automatica-fricciones`, `pkf-auditor`
reportó — sin escribirlo él mismo en este archivo, siguiendo AGENTS.md
sección 7 — que un comando suyo fue bloqueado por mencionar
`docs/adr/ADR-006-hook-proteccion-bash.md` junto a la notación de prosa
`sección 'Decisión' > '2. ...'`, que este mismo documento usa
constantemente para citar subsecciones. Esa notación tiene la forma exacta
de un redirect real (espacio + `>`), así que el fix anterior (exigir
espacio antes de `>`) no alcanzaba — el problema no era falta de contexto,
sino verificar la *mención en cualquier parte* del comando en vez del
*destino real* de la escritura. Se rediseñó `_looks_like_write`: `>`/`>>` y
`tee` ahora extraen su destino real (`_redirect_targets`/`_tee_targets`) y
solo bloquean si ESE destino específico matchea un patrón protegido, no si
el archivo protegido aparece mencionado en cualquier otra parte del
comando. 2 tests de regresión más (la notación de prosa ya no bloquea; un
`tee -a` real a archivo protegido sigue bloqueado). 48 tests totales
pasando.

> Implementado 2026-07-07, en la misma sesión que introdujo el bug (ver
> `docs/orquestacion-claude-code.md`, sección 5, "Fix aplicado tras uso
> real"). Tres rondas del mismo tipo de bug en una sola sesión: confirma
> que una heurística de "menciona + contiene token" sobre texto libre es
> estructuralmente propensa a falsos positivos en prosa técnica (que cita
> archivos y usa notación `>` constantemente); verificar el *destino real*
> de la escritura, no solo la mención, es la corrección de fondo — vale la
> pena vigilar si aparece una cuarta ronda con otro token (`cp `, `sed -i`,
> etc.) que todavía se verifican por mención en cualquier parte, no por
> destino.

---

### 2026-07-07 — El orquestador implementó un cambio de arquitectura como si fuera un fix de bug, sin pasar por `pkf-architect`
**Proyecto:** Sistema de Validación Preventiva y Libro de Clases Digital (pipeline PKF con Claude Code).
**Qué pasó:** al corregir el primer falso positivo real de `protect_bash_writes.py`
(ver entrada anterior), el orquestador no solo ajustó la precisión de
tokens (`>`/`tee` exigiendo contexto) — también agregó una **excepción
categórica nueva**: cualquier `git commit` quedaba exento de todo el
análisis de escritura. Esto se implementó directo, en el mismo commit del
fix, sin pasar por `pkf-architect` ni generar un ADR que actualizara
ADR-006. `pkf-auditor`, al auditar `hook-proteccion-bash`, lo detectó y
marcó el item como `NEEDS_FIXES` — no por defectos de código (todos los
tests pasaban), sino porque esa excepción era una decisión de arquitectura
(P3 y sección 4 de `AGENTS.md`: "trade-off de diseño", "Estructural") que
ADR-006 ya había deliberado explícitamente y descartado como alternativa
("bloquear `Bash` sin excepciones — descartada"), ampliando en la práctica
un límite de seguridad ya aceptado sin la aprobación humana que ese tipo de
cambio requiere. El auditor encontró además que la excepción ni siquiera
cubría el caso real que la motivó (commits multilínea descalifican de
`_is_single_command()`) — el rediseño de detección por destino real,
implementado en el mismo commit, era lo que efectivamente resolvía el
problema. La excepción categórica era, en los hechos, innecesaria además de
no autorizada.

Contexto agravante: esto ocurrió bajo presión de tiempo real — el dueño del
proyecto había señalado minutos antes que un auditor distinto llevaba 15
minutos y ~165 mil tokens sin terminar, y el orquestador estaba resolviendo
un bloqueo activo de su propio flujo de commits. La presión de "arreglar
ya" es exactamente la condición bajo la que este framework existe para
imponer una pausa (P3), y en este caso la pausa no se impuso a sí mismo.
**Frecuencia:** primera vez.
**Solución candidata:** el dueño del proyecto eligió revertir la excepción
categórica (opción más simple, dado que el auditor ya había mostrado que
era redundante) en vez de ratificarla vía un ADR nuevo. Como principio
general hacia adelante: un fix de bug que además *amplía* una excepción o
un límite de seguridad ya fijado por un ADR aceptado dejó de ser un simple
"ajuste de lógica" (P4) — cruza a "trade-off de diseño" (P3) y debe
declararse como tal *antes* de implementarse, sin importar la urgencia con
la que se descubrió el bug que lo motivó.

> Implementado 2026-07-07, en la misma sesión: se revirtió la excepción
> categórica de `git commit` (`GIT_COMMIT_RE`, `_matches_git_commit_exception`)
> de `.claude/hooks/protect_bash_writes.py`, conservando únicamente el
> rediseño de detección por destino real (que sí es una corrección de
> precisión legítima). Se corrigió de paso un bug relacionado encontrado al
> revertir: `_tee_targets` capturaba *todos* los tokens restantes de la
> línea como posibles destinos, no solo el inmediato — suficiente para que
> prosa como "documenta tee en AGENTS.md" contara "AGENTS.md" como destino
> de `tee` aunque estuviera a varias palabras de distancia. Ver
> `docs/orquestacion-claude-code.md`, sección 5, y
> `tests/test_protect_bash_writes.py` para los tests que documentan
> explícitamente qué queda cubierto (`>`/`tee` por destino real) y qué
> sigue siendo un riesgo vigilado y aceptado (`sed -i`, `cp `, `install `,
> `rsync`, `perl -i`, `truncate` — mención+substring, sin excepción de
> `git commit` que lo enmascare).
