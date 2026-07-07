# ADR-005 — Captura de fricciones como paso explícito de cierre de tarea, reforzado por un hook `Stop` acotado

**Fecha:** 2026-07-07
**Estado:** aceptada

## Contexto

`docs/friction-log.md` (entrada 2026-07-07, "La captura de fricciones
depende de que el dueño del proyecto se acuerde de preguntar, no ocurre por
iniciativa propia") registró que, durante toda una sesión de trabajo con
PKF (instalación del kit, specs, ADRs, RN, implementación de scaffold),
ninguna fricción se propuso por iniciativa de la IA. Las tres entradas de
fricción de ese mismo día solo existen porque el dueño del proyecto preguntó
explícitamente al cierre de la sesión — y una de esas tres era un bug real
(permisos faltantes en `pkf-spec`) que se habría perdido de no preguntar.
Esto contradice el principio fundacional de PKF ("el framework crece por
extracción", `docs/friction-log.md`, encabezado), que presupone que la
extracción ocurre como parte natural del flujo, no como algo que depende de
que un humano la pida al final.

`specs/captura-automatica-fricciones.md` evaluó las tres soluciones
candidatas ya anotadas en esa entrada (paso explícito en `AGENTS.md`, hook
`Stop`, hábito humano documentado) sin decidir por cuenta propia, y dejó
explícita una tensión técnica real: un hook `Stop` puro solo puede inyectar
un recordatorio que el agente lee en su *siguiente* turno — no puede forzar
"reflexión" en el instante exacto de cerrar una tarea — y si dispara en
cada turno de una conversación larga puede volverse ruidoso.

El dueño del proyecto ya decidió, a partir de esa spec, el mecanismo
concreto (no se reabre aquí, se formaliza):

1. Un paso explícito nuevo en `AGENTS.md` que pida proponer candidatas a
   friction-log antes de cerrar cualquier tarea **Normal** o **Estructural**
   (tabla de la sección 4 de `AGENTS.md`).
2. Un hook `Stop` nuevo en `.claude/hooks/`, acotado: no dispara en cada
   turno, sino solo cuando la sesión tuvo ediciones a `specs/`,
   `docs/adr/DRAFT-*.md` o `docs/business-rules.md`.
3. `docs/friction-log.md` **no** se agrega a `PROTECTED_PATTERNS` de
   `.claude/hooks/protect_files.py` — se mantiene sin bloqueo técnico, para
   no contradecir el objetivo de bajar la fricción de captura.
4. El agente **nunca** escribe una entrada nueva en `docs/friction-log.md`
   en silencio: antes de documentar (o decidir no documentar) una fricción
   candidata, debe anunciarla explícitamente al dueño del proyecto —
   mostrando qué encontró y su intención — como parte de su respuesta. Este
   requisito es explícito del dueño del proyecto y debe quedar en el propio
   texto de `AGENTS.md`, no solo anotado aquí.

**Verificación de consistencia con decisiones ya aceptadas:** se revisaron
ADR-001, ADR-002, ADR-003, ADR-004 y `docs/business-rules.md` (RN-001,
RN-002, RN-003) contra este mecanismo. No se detectó contradicción:

- ADR-002 ya estableció el patrón de hooks nativos de Claude Code
  (`SessionStart`, `PreToolUse`, `PostToolUse`) como forma de que PKF se
  aplique sin depender de que el agente "recuerde" — un hook `Stop` nuevo
  extiende ese mismo patrón a un evento no usado hasta ahora, no lo
  contradice.
- ADR-002 registró como alternativa descartada "Bloquear también `Bash` en
  el hook de protección" y dejó anotado en
  `docs/orquestacion-claude-code.md` sección 5 que `protect_files.py` solo
  cubre `Edit`/`Write`, no `Bash`, **a propósito**, para no interferir con
  el `mv`/`git mv` humano de promoción de ADR. El mecanismo aquí propuesto
  respeta esa decisión: el hook `Stop` no bloquea ni intercepta `Bash`, solo
  lee la señal de qué se editó durante la sesión (ver "Decisión" y
  "Consecuencias" — incluyendo la limitación de que esta señal, basada en
  llamadas a `Edit`/`Write`, no cubre escrituras vía `Bash`, el mismo hueco
  ya documentado en la entrada de friction-log 2026-07-07 "La protección de
  archivos (hook `PreToolUse`) no cubre `Bash`" y que es objeto del item de
  cola independiente `hook-proteccion-bash`, no de este ADR).
- No hay ninguna RN (RN-001/002/003) que este mecanismo toque: son reglas
  del dominio de negocio (asistencia/cursos), sin relación con el
  framework PKF.
- El nombre de archivo del hook nuevo y su registro en
  `.claude/settings.json`/`docs/orquestacion-claude-code.md` siguen el
  mismo patrón que los tres hooks ya existentes (ver "Decisión").

No se encontró conflicto que detener y reportar; se procede a formalizar.

## Decisión

Adoptar la combinación de Opción 1 (paso explícito en `AGENTS.md`) +
Opción 2 acotada (hook `Stop` condicionado) ya decidida por el dueño del
proyecto, con el requisito de "nunca escribir en silencio" incorporado al
texto de `AGENTS.md`. La Opción 3 (hábito humano documentado sin refuerzo
técnico) no se adopta sola porque es, literalmente, el statu quo que ya
produjo la fricción documentada.

### 1. Texto a agregar a `AGENTS.md`

Se propone agregar una sección nueva **7** (después de la sección 6 actual,
antes del pie de página "*Este proyecto usa PKF...*"), con este texto
exacto — a revisar y aprobar por el dueño del proyecto; ningún agente lo
escribe sin mostrar antes el diff completo, por P2 y sección 5 de
`AGENTS.md`:

> ## 7. Antes de cerrar una tarea Normal o Estructural
>
> Antes de dar por cerrada cualquier tarea clasificada como **Normal** o
> **Estructural** (tabla de la sección 4), cualquier agente (el
> orquestador principal o un subagente PKF) debe revisar si encontró
> alguna fricción real durante el trabajo — algo que no encontró donde
> esperaba, una convención que estorbó, un permiso faltante, una
> ambigüedad que tuvo que resolver por su cuenta, etc. — y proponerla
> explícitamente como candidata a `docs/friction-log.md`, en vez de
> esperar a que el dueño del proyecto pregunte.
>
> Esto no reemplaza el juicio humano: el agente **nunca escribe una
> entrada nueva en `docs/friction-log.md` en silencio**. Antes de
> documentar (o de decidir no documentar) una fricción candidata, debe
> anunciarla explícitamente al dueño del proyecto como parte de su
> respuesta — mostrando qué encontró y cuál es su intención (documentarla
> o no, y con qué severidad) — y esperar confirmación o instrucción antes
> de escribir la entrada. Si la tarea no tuvo ninguna fricción real que
> valga la pena anotar, basta con decirlo explícitamente ("no encontré
> fricciones dignas de registrar en esta tarea") en vez de omitir el paso
> sin mencionarlo.
>
> Si trabajas en Claude Code, un hook `Stop`
> (`.claude/hooks/stop_friction_reminder.py`, ver
> `docs/orquestacion-claude-code.md`) refuerza este paso técnicamente
> cuando detecta ediciones a `specs/`, `docs/adr/DRAFT-*.md` o
> `docs/business-rules.md` durante la sesión — pero el hook solo puede
> recordarlo en el turno siguiente, no reemplaza este paso ni te exime de
> seguirlo cuando trabajas fuera de una sesión con hooks activos.

### 2. Diseño del hook `Stop`

- **Archivo:** `.claude/hooks/stop_friction_reminder.py` (Python, mismo
  criterio que `protect_files.py`: necesita parsear JSON/JSONL, más simple
  que en `bash`).
- **Registro en `.claude/settings.json`:** nuevo bloque `"Stop"` análogo a
  los tres existentes:
  ```json
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/stop_friction_reminder.py"
        }
      ]
    }
  ]
  ```
- **Entrada que recibe (según el contrato documentado de hooks `Stop` de
  Claude Code):** JSON por stdin con, entre otros campos, `session_id`,
  `transcript_path` (ruta al archivo JSONL con la transcripción completa
  de la sesión, incluyendo los `tool_use` — con su `tool_name` e `input`,
  el mismo `file_path` que ya usa `protect_files.py` para `Edit`/`Write`) y
  `stop_hook_active` (booleano: `true` si Claude Code ya está en un ciclo
  de continuación disparado por un `Stop` hook previo en este mismo turno,
  para evitar loops infinitos).
- **Lógica:**
  1. Si `stop_hook_active` es `true`, salir inmediatamente con código 0 sin
     imprimir nada (evita re-disparar el mismo recordatorio en bucle: ya se
     mostró una vez en este ciclo).
  2. Leer `transcript_path` y parsear el JSONL línea por línea, buscando
     entradas de tipo `tool_use` con `tool_name` en `{"Edit", "Write"}`
     cuyo `input.file_path` matchee alguno de estos patrones (mismo estilo
     de regex que `PROTECTED_PATTERNS` de `protect_files.py`):
     - `(^|/)specs/.*\.md$`
     - `(^|/)docs/adr/DRAFT-.*\.md$`
     - `(^|/)docs/business-rules\.md$`
  3. Si no hay ninguna coincidencia: salir con código 0, sin imprimir nada
     — no hay señal de trabajo no trivial en la sesión, no interrumpe.
  4. Si hay al menos una coincidencia: salir con **código 2** e imprimir en
     stderr un recordatorio (mismo mecanismo que usa `protect_files.py`
     para bloquear, adaptado aquí a "no dejar terminar sin preguntar", no a
     "bloquear una escritura"), por ejemplo:
     `[PKF] Esta sesión editó specs/, un DRAFT de ADR o business-rules.md.`
     `Antes de cerrar: ¿hay alguna fricción real de esta sesión que valga`
     `la pena proponer a docs/friction-log.md? Si sí, anúnciala` `explícitamente (qué encontraste + tu intención) antes de` `documentarla — nunca la escribas en silencio (AGENTS.md sección 7).`
     `Si no hay ninguna, dilo explícitamente y continúa.`
     Un exit code 2 en un hook `Stop` de Claude Code impide que la sesión
     termine y entrega el stderr como contexto para el turno siguiente —
     el mismo patrón de "bloqueo real" que ya usa `protect_files.py` en
     `PreToolUse`, aplicado aquí al evento `Stop`.
  5. Cualquier error de parseo (JSON inválido, `transcript_path` inexistente
     o ilegible) se trata igual que en `protect_files.py`: no bloquear por
     un problema del propio hook — salir con código 0.
- **Qué hace si no detecta señal de trabajo no trivial:** nada — sale en
  silencio con código 0. Es la pieza central de "acotado, no en cada turno"
  que pidió el dueño del proyecto: sesiones que no tocaron `specs/`,
  `docs/adr/DRAFT-*.md` ni `docs/business-rules.md` no ven ningún
  recordatorio.
- **Por qué transcript y no `git diff`:** se evaluaron ambas señales (ver
  "Alternativas consideradas"). Se elige parsear `transcript_path` porque
  está acotado exactamente a la sesión actual (vía `session_id`), a
  diferencia de `git diff`/`git status`, que reflejaría también cambios sin
  commit que ya existían en el árbol de trabajo antes de que la sesión
  empezara, o que otra sesión/persona haya dejado a medio hacer — una señal
  más ruidosa y menos confiable para "¿hubo trabajo no trivial *en esta
  sesión*?".

### 3. `docs/friction-log.md` no se agrega a `PROTECTED_PATTERNS`

Se mantiene explícitamente **fuera** de `PROTECTED_PATTERNS` en
`.claude/hooks/protect_files.py`. Añadirlo bloquearía justamente la
escritura que este mecanismo busca facilitar (proponer y registrar
fricciones), contradiciendo el objetivo. El guardrail contra escritura
apresurada o no anunciada no es técnico aquí — es el paso 4 de esta
decisión (nunca escribir en silencio, anunciar antes), ya incorporado al
texto de `AGENTS.md` propuesto arriba.

### 4. Actualización pendiente en `docs/orquestacion-claude-code.md`

Cuando `pkf-implementer` construya esto, debe agregar `stop_friction_reminder.py`
a la lista de "Qué instala" (sección 1) y a la tabla de la sección 2 de
`docs/orquestacion-claude-code.md`, siguiendo el mismo patrón usado para
`SessionStart`/`PreToolUse`/`PostToolUse` (criterio de aceptación del spec
de origen).

### 5. Actualización de la entrada de friction-log que motivó esta spec

Cuando este ADR se acepte e implemente, la entrada
`### 2026-07-07 — La captura de fricciones depende de que el dueño del
proyecto se acuerde de preguntar, no ocurre por iniciativa propia` de
`docs/friction-log.md` debe marcarse (no borrarse) indicando qué solución
se adoptó y cuándo, siguiendo la convención de "marcar, no eliminar" de
`docs/CONVENTIONS.md` — tarea de `pkf-implementer`, no de este ADR.

## Alternativas consideradas

- **Solo Opción 1 (paso en `AGENTS.md`), sin hook** — descartada por el
  dueño del proyecto (no reabierta aquí): más barata, pero sigue
  dependiendo de que el propio agente recuerde seguir una instrucción en
  prosa en el momento de cerrar — exactamente el patrón de fragilidad que
  originó la fricción, solo que ahora escrito.
- **Solo Opción 2 (hook `Stop`), sin paso en `AGENTS.md`** — descartada por
  el dueño del proyecto (no reabierta aquí): un guardrail técnico sin la
  instrucción explícita en `AGENTS.md` deja al agente sin saber *qué* se
  espera que haga cuando el hook lo interrumpe (el texto de la sección 7
  es lo que le da contenido accionable al recordatorio del hook).
- **Opción 3 sola (hábito humano documentado, sin Opción 1 ni 2)** —
  descartada: formaliza por escrito el statu quo que ya produjo la
  fricción (el dueño del proyecto preguntando al final); no resuelve la
  dependencia de la memoria humana que es la causa raíz documentada.
- **Hook `Stop` sin acotar (dispara en cada turno)** — descartada por el
  dueño del proyecto: el propio spec de origen advierte que sería ruidoso
  en una conversación larga; se prefiere condicionarlo a señales concretas
  de edición de archivos de alto impacto para PKF.
- **Detectar la señal de "trabajo no trivial" via `git diff`/`git status`
  del working tree en vez de `transcript_path`** — descartada como
  mecanismo principal: es una señal de todo el árbol de trabajo, no de la
  sesión actual — puede dar falsos positivos (cambios sin commit de una
  sesión anterior o de edición manual del dueño del proyecto, aún visibles
  en `git diff`, disparando el recordatorio sin que esta sesión haya hecho
  nada) y falsos negativos si algo se edita y se revierte al mismo
  contenido dentro de la sesión (el diff queda vacío aunque hubo trabajo e
  intentos). Queda anotada como alternativa de respaldo: si al implementar
  se descubre que `transcript_path` no es legible, no tiene el campo
  `input.file_path` esperado, o cambia de formato entre versiones de
  Claude Code, `pkf-implementer` puede recurrir a `git diff --name-only`
  como señal de reemplazo — debe documentarse esa desviación si ocurre.
- **Hook `SessionEnd` en vez de `Stop`** — descartada: el propio spec de
  origen deja este dato como no negociable: `SessionEnd` corre después de
  que la sesión ya terminó, sin ningún turno de conversación posterior
  donde la IA pueda leer un recordatorio y responder — no hay inferencia
  posible en ese momento, así que no puede lograr el objetivo de que el
  agente proponga algo.
- **Agregar `docs/friction-log.md` a `PROTECTED_PATTERNS`** — descartada
  explícitamente por el dueño del proyecto: contradice el objetivo de
  bajar la fricción de captura: exigiría que cada entrada pasara por el
  mismo bloqueo de `Edit`/`Write` que hoy protege `AGENTS.md` o
  `business-rules.md`, cuando lo que se busca es lo opuesto — que proponer
  una entrada sea fácil. El guardrail contra escritura no anunciada se
  resuelve por el requisito de "nunca en silencio" (paso 4), no por un
  bloqueo técnico de escritura.

## Consecuencias

**Se gana:** un paso explícito y escrito en `AGENTS.md` que cualquier
agente (principal o subagente) puede seguir sin depender de que el dueño
del proyecto pregunte; un guardrail técnico adicional (hook `Stop`) que no
depende de la "memoria" del agente para las sesiones donde sí se tocó
`specs/`, un `DRAFT` de ADR o `business-rules.md`; ausencia de ruido en
sesiones triviales (el hook no dispara si no hay señal); y un requisito
explícito de transparencia (nunca escribir en `friction-log.md` sin
anunciarlo primero) que evita el riesgo simétrico de que, al bajar la
fricción de captura, aparezcan entradas de baja calidad o no revisadas.

**Se pierde / se acepta (riesgos, honestos):**

- **Límite técnico fundamental, ya anticipado en el spec de origen y no
  resuelto por ningún hook:** un hook `Stop` no puede forzar "reflexión" en
  el instante exacto de cerrar la tarea. Solo puede impedir que la sesión
  termine y entregar un mensaje que la IA lee — y actúa — en el turno
  *siguiente*. Si el agente, en ese turno siguiente, decide (incorrecta o
  superficialmente) que no hay fricción y responde eso sin verdadera
  reflexión, el hook no tiene forma de verificar la calidad de esa
  respuesta ni de exigir una segunda pasada. El guardrail técnico fuerza
  que *se pregunte*, no que la respuesta sea buena.
- **Riesgo de bucle molesto si `stop_hook_active` no se maneja bien:**
  si la lógica de "no re-disparar" falla o el agente responde al
  recordatorio sin que la sesión dispare `Stop` de nuevo en un estado que
  el hook reconozca como ya atendido, existe riesgo de loop. Se mitiga con
  el chequeo de `stop_hook_active` descrito en el diseño, pero
  `pkf-implementer` debe probarlo explícitamente en una sesión real antes
  de darlo por cerrado (no basta con leerlo).
- **Gap conocido y ya documentado, no resuelto por este ADR:** la señal del
  hook se basa en llamadas a las herramientas `Edit`/`Write` en el
  transcript. Una escritura a `docs/business-rules.md` (o a cualquier
  archivo protegido) hecha vía `Bash` (por ejemplo un heredoc, como ya
  ocurrió en esta misma sesión de trabajo según
  `docs/friction-log.md` 2026-07-07 "La protección de archivos (hook
  `PreToolUse`) no cubre `Bash`") **no** dispararía este recordatorio,
  porque el `tool_name` registrado sería `Bash`, no `Edit`/`Write`. Ese
  hueco es responsabilidad del item de cola independiente
  `hook-proteccion-bash` (`specs/hook-proteccion-bash.md`, ya en
  `READY_FOR_ARCH`), no de este ADR — se deja anotado aquí para que quede
  trazable, sin intentar resolverlo en este documento.
- **Dependencia de un detalle no verificado en producción:** el diseño
  asume que `transcript_path` es un JSONL legible con entradas `tool_use`
  que incluyen `tool_name` e `input.file_path` en el mismo formato que ya
  usa `protect_files.py` para `Edit`/`Write` vía `PreToolUse`. Esto es
  consistente con el contrato documentado de hooks de Claude Code, pero
  `pkf-implementer` debe verificarlo leyendo un `transcript_path` real
  durante la implementación, no asumirlo solo por este ADR — si el formato
  difiere, aplicar la alternativa de respaldo (`git diff --name-only`)
  anotada arriba y documentar la desviación.
- **Más piezas que mantener:** un cuarto hook (`Stop`) se suma a los tres
  ya existentes (`SessionStart`, `PreToolUse`, `PostToolUse`), ampliando la
  superficie de `.claude/hooks/` y `.claude/settings.json` que el dueño del
  proyecto —equipo de una persona— debe entender y mantener (riesgo ya
  general de ADR-001/ADR-002, aquí se agrega una unidad más).
- **El requisito de "nunca en silencio" agrega fricción deliberada a la
  escritura de `friction-log.md`**, en tensión leve con el objetivo general
  de "bajar la fricción de captura": se acepta a propósito, por instrucción
  explícita del dueño del proyecto, priorizando calidad/transparencia de
  las entradas sobre velocidad de escritura.

**Qué revisar si el contexto cambia:** si Claude Code cambia el contrato de
datos que entrega a hooks `Stop` (campos disponibles, formato de
`transcript_path`), o si se resuelve `hook-proteccion-bash` de forma que
cambie qué herramienta registra escrituras a rutas protegidas, este ADR
debe revisarse.

## Referencias

- `specs/captura-automatica-fricciones.md` — spec de origen de esta
  propuesta.
- `docs/friction-log.md`, entrada 2026-07-07 — "La captura de fricciones
  depende de que el dueño del proyecto se acuerde de preguntar, no ocurre
  por iniciativa propia" (motivo de esta spec/ADR).
- `docs/friction-log.md`, entrada 2026-07-07 — "La protección de archivos
  (hook `PreToolUse`) no cubre `Bash`" (gap conocido, no resuelto aquí; ver
  item de cola `hook-proteccion-bash`).
- ADR-002 — Orquestación de PKF con hooks y subagentes de Claude Code
  (define el patrón de hooks nativos que este ADR extiende con `Stop`, y
  la decisión ya aceptada de no bloquear `Bash` en `protect_files.py`).
- `docs/orquestacion-claude-code.md` — guía operativa de hooks; a
  actualizar por `pkf-implementer` con el hook `Stop` nuevo.
- `.claude/hooks/protect_files.py` — patrón de referencia para
  `PROTECTED_PATTERNS`, manejo de errores de parseo, y estilo de mensaje al
  agente, reusado en el diseño del hook `Stop`.
- ADR-001 — Adoptar PKF v0.1 (contexto de "el framework crece por
  extracción", principio que esta decisión busca hacer cumplir en la
  práctica).
