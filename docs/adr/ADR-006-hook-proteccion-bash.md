# ADR-006 — Hook `PreToolUse` sobre `Bash` con bloqueo real y excepciones auditables

**Fecha:** 2026-07-07
**Estado:** aceptada

## Contexto

`docs/friction-log.md` (entrada 2026-07-07, "La protección de archivos (hook
`PreToolUse`) no cubre `Bash`") registra que `.claude/hooks/protect_files.py`
solo intercepta las herramientas `Edit`/`Write` sobre `AGENTS.md`,
`docs/business-rules.md` y ADRs ya aceptados (`docs/adr/ADR-\d{3}-*.md`).
ADR-002 dejó `Bash` fuera de ese guardrail a propósito, para permitir el
`mv`/`git mv` humano de promoción de ADR (`docs/adr/DRAFT-<slug>.md` →
`docs/adr/ADR-0XX-<slug>.md`, ver `docs/orquestacion-claude-code.md` sección
4). Pero en la práctica ese mismo hueco se usó, en la misma sesión, para un
caso más amplio: crear RN-001, RN-002 y RN-003 directamente en
`docs/business-rules.md` vía un heredoc de `Bash`, evitando por completo el
guardrail que sí protege `Edit`/`Write` sobre ese archivo. La única barrera
real en ese camino fue que el agente decidiera mostrar el diff antes de
guardar — exactamente el problema que motivó crear los hooks de
`PreToolUse` en primer lugar (ADR-002, sección Contexto: "un bloqueo real,
no una sugerencia").

`specs/hook-proteccion-bash.md` deja explícita la tensión central: cualquier
hook sobre `Bash` que bloquee escrituras a rutas protegidas corre el riesgo
de bloquear también el `mv`/`git mv` legítimo de promoción de ADR que
ADR-002 protegió deliberadamente, y de no ser una señal "confiable" porque
`Bash` (a diferencia de `Edit`/`Write`) no entrega un `file_path` discreto
en el JSON del evento — solo un string de comando de shell arbitrario.

**Decisión ya tomada por el dueño del proyecto (no se reabre aquí, se
formaliza):** el mecanismo elegido es **"Bloqueo real con excepciones
auditables"** — un hook `PreToolUse` nuevo sobre `Bash` que bloquea (código
de salida 2) comandos que escriban directamente sobre las rutas de
`PROTECTED_PATTERNS`, con dos excepciones explícitas: (1) el `mv`/`git mv`
de promoción de ADR, y (2) la invocación del script sancionado
`tools/add_business_rule.py` como único camino legítimo para crear/
modificar RN vía `Bash`. La promoción de ADR **no** se automatiza (no se
construye `tools/promote_adr.py`); se mantiene manual.

Se revisaron `docs/business-rules.md`, ADR-001, ADR-002, ADR-003 y ADR-004
contra este spec: no se detectó ninguna contradicción. ADR-002 ya anticipó
este paso como "siguiente paso, no incluido aún" (`docs/
orquestacion-claude-code.md` sección 5) y lo dejó explícitamente como
alternativa descartada "por ahora" en su propia sección "Alternativas
consideradas" — este ADR es esa revisión, tal como ADR-002 mismo anotó que
correspondería hacer si se automatiza más el pipeline.

## Decisión

Agregar un hook `PreToolUse` nuevo, `.claude/hooks/protect_bash_writes.py`,
registrado en `.claude/settings.json` con `matcher: "Bash"`, que se ejecuta
antes de cada invocación de `Bash` y decide bloquear (código de salida 2) o
dejar pasar (código de salida 0) según la lógica siguiente. El mensaje de
error en `stderr` sigue el mismo estilo que `protect_files.py` (bloqueo real
explicado, con la alternativa legítima indicada).

### 1. Lógica de detección (heurística explícita, no una señal perfecta)

El hook recibe el JSON del evento y lee `tool_input.command` (el string de
shell completo). La lógica, en orden:

1. **Short-circuit barato (responde a la pregunta abierta 5):** si
   `tool_name != "Bash"`, sale con 0 de inmediato. Si `tool_name == "Bash"`,
   busca en el string del comando, con `re.search`, si aparece **alguno**
   de los mismos patrones de `PROTECTED_PATTERNS` que ya usa
   `protect_files.py` (`AGENTS\.md`, `docs/business-rules\.md`,
   `docs/adr/ADR-\d{3}-.*\.md`). Si **ninguno** aparece, sale con 0 de
   inmediato, sin ningún análisis adicional. Esto significa que comandos
   frecuentes y legítimos (`pytest`, `git status`, `python
   tools/check_refs.py`, `git log`, `ls`, etc.) nunca mencionan esos
   nombres de archivo y terminan aquí, sin ningún costo ni riesgo de falso
   positivo — el matcher `"Bash"` en `settings.json` dispara el hook en
   cada invocación, pero el hook mismo descarta el 99% de los casos en este
   primer chequeo.
2. **Excepción 1 — promoción de ADR (responde a la pregunta abierta 1):**
   si el comando, **completo y sin ningún separador de shell adicional**
   (sin `;`, `&&`, `||`, `|`, backticks, `$(...)`, ni saltos de línea fuera
   de un trailing newline), matchea exactamente el patrón
   `^(git\s+mv|mv)\s+(\S*/)?DRAFT-([a-z0-9-]+)\.md\s+(\S*/)?ADR-\d{3}-\3\.md\s*$`
   — es decir, un `mv`/`git mv` de dos argumentos donde el origen es
   `DRAFT-<slug>.md`, el destino es `ADR-0XX-<slug>.md`, y **el `<slug>` es
   idéntico en origen y destino** — se permite (exit 0).
   Esta es la señal más "confiable" disponible dado que `Bash` no entrega
   un `file_path` discreto como sí lo hace `Edit`/`Write`: no es perfecta
   (sigue siendo una coincidencia de texto), pero es **estrecha y de un solo
   propósito** — exige forma exacta de dos argumentos, exige que no venga
   encadenada con nada más (lo que evita el caso "`git mv DRAFT-x.md
   ADR-0XX-x.md && echo texto >> docs/business-rules.md`", que **sí** se
   bloquea porque el comando completo ya no matchea el patrón de excepción),
   y exige que el slug coincida, evitando el caso "renombrar cualquier
   archivo como si fuera cualquier ADR".
3. **Excepción 2 — script sancionado (responde a la pregunta abierta 1 y a
   la 2):** si el comando, también completo y sin encadenar con otros
   separadores de shell, matchea
   `^(python3?|py)\s+tools/add_business_rule\.py\b.*$`, se permite (exit
   0). La validación de fondo (qué argumentos son válidos, qué se escribe)
   la hace el propio script, no el hook — ver sección 2 más abajo.
4. **Bloqueo (caso general):** si el comando menciona alguno de los
   patrones protegidos (paso 1) y no calzó con ninguna de las dos
   excepciones (pasos 2–3), se evalúa si el comando "parece" una escritura:
   contiene alguno de los tokens `>`, `>>`, `sed -i`, `tee`, `cp `,
   `install `, `rsync`, `dd `, `perl -i`, `truncate`, o un `mv`/`git mv`
   que no calzó exactamente con la excepción 1. Si aparece un nombre de
   archivo protegido **y** alguno de estos tokens, se bloquea con exit 2.
   Si aparece el nombre de archivo pero ningún token de escritura (p. ej.
   `cat docs/business-rules.md`, `grep RN-001 docs/business-rules.md`,
   `git diff AGENTS.md`), se permite — son operaciones de lectura.

### 2. Diseño de `tools/add_business_rule.py` (decisión de arquitectura, sin implementar)

Único camino legítimo para crear u obsoletar una RN vía `Bash` dentro de una
sesión de Claude Code, invocado con instrucción explícita del dueño del
proyecto (P2 de `AGENTS.md`). Es un script Python de línea de comandos con
dos subcomandos:

**`create`** — crear una RN nueva:

```
python tools/add_business_rule.py create \
  --numero 004 \
  --titulo "Título corto de la regla" \
  --regla "Enunciado preciso, verificable, sin ambigüedad." \
  --origen "Contrato / cliente / normativa / decisión interna (referencia)." \
  [--fecha 2026-07-08]
```

Validaciones antes de escribir nada (si cualquiera falla, el script termina
con código distinto de cero, mensaje claro en `stderr`, y **no toca el
archivo**):

- `docs/business-rules.md` existe y contiene la línea `**Próximo número
  disponible:** NNN` en el formato esperado (parseable con una sola regex).
- `--numero` (obligatorio, formato `NNN` de 3 dígitos) **coincide
  exactamente** con el valor actual de "Próximo número disponible". Si no
  coincide, el script aborta e informa cuál es el número real vigente —
  esto responde al requisito de que el propio comando de `Bash` sea
  autodescriptivo y auditable en el historial de la sesión (el número
  deseado queda explícito en el comando, no se infiere en silencio), y
  evita una condición de carrera si dos invocaciones creen RN casi
  simultáneas.
- `--titulo`, `--regla`, `--origen` no vacíos, sin saltos de línea, y sin
  contener las secuencias `### RN-` ni `**Estado:**` (evita que alguien use
  estos campos para inyectar un bloque Markdown completo o alterar el
  `Estado` de otra RN existente desde un campo de texto).
- `--fecha` (opcional, `AAAA-MM-DD`; por defecto la fecha del sistema) debe
  ser una fecha válida en ese formato.

Si todas las validaciones pasan, el script:

- Construye el bloque exactamente en el formato de `docs/CONVENTIONS.md`
  ("Formato de una regla de negocio"), con `**Estado:** vigente` y
  `**Historial:**\n- <fecha> — creada.`.
- Inserta ese bloque al final de la lista de RN existentes (antes del
  comentario `<!-- PLANTILLA ... -->`), preservando todo el contenido
  anterior sin tocarlo (P5 de `AGENTS.md` — nunca se borra historia).
- Actualiza la línea `**Próximo número disponible:**` a `--numero + 1`,
  con cero-padding a 3 dígitos.
- Escribe de forma atómica (archivo temporal + `os.replace`), para no dejar
  el archivo a medio escribir si algo falla a mitad de la escritura.
- Imprime en `stdout` un resumen de lo escrito (equivalente a un diff), para
  que quede en el historial de la sesión de Claude Code sin necesidad de
  leer el archivo aparte.

**`deprecate`** — marcar una RN existente como obsoleta (nunca se borra ni
reescribe el enunciado original, solo se actualiza `Estado:` y se agrega una
línea a `Historial:`, según `docs/CONVENTIONS.md`, "Marcar contenido
obsoleto"):

```
python tools/add_business_rule.py deprecate \
  --numero 002 \
  --reemplazada-por RN-0NN \
  [--fecha 2026-07-08]
```

Validaciones: la RN `--numero` existe en el archivo y su `Estado:` actual es
`vigente` (no se puede obsoletar dos veces); si se da
`--reemplazada-por`, su formato es `RN-NNN`. Escritura: cambia únicamente la
línea `**Estado:** vigente` de ese bloque a `**Estado:** obsoleta
(reemplazada por RN-NNN, <fecha>)` y agrega una línea al `Historial:` del
mismo bloque (`- <fecha> — marcada obsoleta, reemplazada por RN-NNN.`). El
resto del archivo, incluido el enunciado original de la regla, no se toca.

**Fuera del alcance del script (limitación reconocida, no resuelta aquí):**
el script no verifica *quién* lo invoca ni si hubo, en efecto, instrucción
explícita del dueño — eso sigue siendo una responsabilidad del agente/sesión
de Claude Code, igual que hoy ocurre con cualquier edición de
`business-rules.md`. El script formaliza el *cómo* (formato, numeración,
atomicidad), no el *quién autoriza*.

### 3. Cambios de configuración necesarios

- `.claude/settings.json`: agregar una entrada nueva a `PreToolUse` con
  `matcher: "Bash"` apuntando a
  `$CLAUDE_PROJECT_DIR/.claude/hooks/protect_bash_writes.py`, sin tocar la
  entrada existente de `"Edit|Write"`.
- Se recomienda (decisión de diseño, detalle de implementación para
  `pkf-implementer`) extraer `PROTECTED_PATTERNS` a un módulo compartido
  (p. ej. `.claude/hooks/protected_patterns.py`) importado tanto por
  `protect_files.py` como por `protect_bash_writes.py`, para no duplicar la
  lista en dos archivos y reducir el riesgo, ya anotado como "vigilado" en
  ADR-002, de que quede desactualizada si se agrega un archivo protegido
  nuevo.

### Respuestas explícitas a las preguntas abiertas de la spec

1. **Señal para distinguir el `mv` legítimo de una escritura directa:**
   resuelto arriba (sección 1, paso 2) — no existe una señal perfecta
   porque `Bash` no expone un `file_path` discreto, pero se usa la señal
   más estrecha posible: coincidencia exacta de un comando de dos
   argumentos `mv`/`git mv` con slug igual en origen y destino, sin
   encadenamiento de shell. Cualquier cosa que se salga de esa forma exacta
   (incluida la variante encadenada con una escritura adicional) cae al
   camino general de bloqueo.
2. **¿Vale la pena una heurística sobre `Bash`, o es la alternativa
   equivocada?** Decisión explícita del dueño del proyecto: sí, con
   excepciones auditables — es el mecanismo "Bloqueo real con excepciones
   auditables" descrito arriba. Se descartan explícitamente, como
   alternativas (ver sección siguiente): (a) dejar `Bash` sin bloqueo por
   patrón y confiar solo en que el script exista como opción — no cierra
   el caso general (heredoc/`sed -i` directo a `AGENTS.md` o a un ADR
   aceptado seguiría sin barrera técnica); (b) un hook `PostToolUse` que
   solo señale sin bloquear — contradice el objetivo explícito de ADR-002
   ("un bloqueo real, no una sugerencia").
3. **¿El script reemplaza la edición humana directa fuera de Claude Code?**
   No, y no podría: ningún hook de Claude Code puede interceptar una
   edición hecha con un editor de texto fuera de una sesión de Claude Code.
   Este guardrail (tanto `protect_files.py` como el hook nuevo) cubre
   **agentes actuando dentro de una sesión de Claude Code**, no ediciones
   humanas directas al filesystem. Eso sigue dependiendo de la disciplina
   ya declarada en P2 de `AGENTS.md` ("solo con instrucción explícita del
   dueño"), fuera del alcance de este ADR.
4. **¿Se automatiza también la promoción de ADR (`tools/promote_adr.py`)?**
   No — decisión explícita del dueño del proyecto, que se formaliza aquí:
   la promoción de ADR se mantiene manual (`mv`/`git mv` + edición manual
   del campo `Estado:`), consistente con la decisión ya tomada en ADR-002
   de que ese paso sea un gesto humano deliberado. No hay fricción
   reportada en `docs/friction-log.md` sobre ese paso específico — la única
   fricción registrada (entrada 2026-07-07) es sobre la creación de RN vía
   heredoc, no sobre la promoción de ADR, que en la misma sesión funcionó
   como estaba previsto (`git mv` para ADR-003 y ADR-004). Ver
   "Alternativas consideradas".
5. **¿Cómo minimizar falsos positivos sobre `Bash` normal?** Resuelto en la
   sección 1, paso 1: el hook nuevo hace un short-circuit barato basado en
   si el comando menciona textualmente alguno de los nombres de archivo
   protegidos. Comandos que no los mencionan (la inmensa mayoría del uso
   normal de `Bash`: tests, `git status`, linter, instalación de paquetes,
   etc.) terminan en el primer chequeo sin análisis adicional ni riesgo de
   bloqueo.

## Alternativas consideradas

- **Dejar `Bash` sin bloqueo directo por patrón, confiando solo en que
  `tools/add_business_rule.py` exista como opción disponible** (primera
  mitad de la pregunta abierta 2 de la spec) — descartada: no cierra el
  caso general que originó la fricción (heredoc/`sed -i`/`tee` directos a
  `AGENTS.md`, `docs/business-rules.md` o un ADR ya aceptado seguirían sin
  ninguna barrera técnica, solo una opción "mejor" coexistiendo con el
  hueco). El dueño del proyecto pidió explícitamente bloqueo real, no una
  opción adicional.
- **Hook `PostToolUse` sobre `Bash` que solo señala (no bloquea) escrituras
  a rutas protegidas** (tercera opción de la pregunta abierta 2) —
  descartada: corre después de que el comando ya se ejecutó (el archivo ya
  fue modificado cuando el hook se entera), y contradice directamente el
  objetivo fundacional de ADR-002 de que la protección sea "un bloqueo
  real, no una sugerencia". Se habría reintroducido exactamente el problema
  que motivó crear los hooks `PreToolUse` en primer lugar.
- **Automatizar la promoción de ADR con `tools/promote_adr.py`** (pregunta
  abierta 4) — descartada por decisión explícita del dueño del proyecto:
  ese paso se mantiene manual porque ADR-002 lo definió deliberadamente
  como gesto humano, y no existe fricción reportada en
  `docs/friction-log.md` sobre ese paso específico que justifique
  automatizarlo ahora (la fricción documentada es sobre RN, no sobre
  ADRs).
- **Distinguir por subagente invocador dentro del hook** (descartada ya por
  la propia spec, sección "Fuera de alcance", citando que ADR-002 ya
  documentó que el JSON de entrada del hook no trae esa información de
  forma confiable) — no se reconsidera aquí.
- **Bloquear `Bash` en bloque para cualquier comando que mencione un
  archivo protegido, sin excepciones** — descartada: habría bloqueado el
  propio flujo de promoción de ADR que ADR-002 protegió explícitamente,
  convirtiendo un guardrail útil en una fricción que rompe un flujo ya
  aceptado.

## Consecuencias

**Se gana:** el caso concreto observado en esta sesión (heredoc de `Bash`
escribiendo directo en `docs/business-rules.md`) queda bloqueado con código
de salida 2, igual de "real" que el bloqueo ya existente para `Edit`/`Write`
(ADR-002). El flujo de promoción de ADR (`git mv DRAFT-<slug>.md
ADR-0XX-<slug>.md`) sigue funcionando sin fricción. Queda un camino legítimo,
auditable y con formato garantizado (`tools/add_business_rule.py`) para
crear/obsoletar RN vía `Bash`, en vez de heredocs libres.

**Se pierde / se acepta — límites honestos de esta heurística (ninguno de
estos es un objetivo cumplido, son huecos conocidos y aceptados):**

- **Falsos negativos por ofuscación de ruta:** cualquier comando que
  construya el nombre del archivo protegido en tiempo de ejecución (variable
  de entorno, `$(echo AGENTS.md)`, concatenación de strings, un script
  Python intermedio invocado con `python -c "open('docs/business-rules.md',
  'a').write(...)"` sin que el nombre del archivo aparezca literal en el
  comando de `Bash`, un script arbitrario en el PATH que internamente
  escriba el archivo) evade la detección por texto. La heurística busca el
  nombre del archivo *literal* en el string del comando; no interpreta
  shell ni sigue redirecciones indirectas.
- **Falsos negativos por herramientas no listadas:** la lista de "tokens de
  escritura" (`>`, `sed -i`, `tee`, etc.) es finita y puede no cubrir una
  herramienta menos común (`ed`, `vim -c`, `awk` con `-i`, un editor de
  línea de comandos distinto). Cualquier herramienta nueva que escriba
  archivos sin usar los tokens listados no se detecta.
- **Falsos positivos posibles (acotados y documentados):** un comando de
  solo lectura que mencione un archivo protegido junto a un token de
  escritura dirigido a *otro* archivo (p. ej. `cat docs/business-rules.md |
  tee /tmp/copia.md`) puede bloquearse aunque no escriba el archivo
  protegido — la heurística no distingue origen de destino dentro del
  comando. Se acepta este costo porque el caso es infrecuente y el mensaje
  de error deja claro cómo proceder (usar la herramienta `Read`, o
  reformular el comando).
- **No es un guardrail perfecto, es una mejora real sobre "nada":** tal
  como ya reconoce `protect_files.py` para `Edit`/`Write` (que tampoco
  puede prevenir toda forma de bypass, solo la vía directa de esas dos
  herramientas), este hook reduce significativamente la superficie del
  hueco observado sin pretender cerrarlo al 100%. Si en el futuro aparece
  un caso de evasión real y repetido, corresponde una nueva entrada en
  `docs/friction-log.md` y, eventualmente, un ADR que lo revise — no
  ampliar la heurística en silencio.
- **Duplicación de `PROTECTED_PATTERNS` entre dos hooks** si no se aplica
  la recomendación de extraerlo a un módulo compartido (sección 3) — riesgo
  vigilado ya anotado en ADR-002, ahora con doble superficie si no se
  factoriza.
- **El guardrail sigue sin cubrir ediciones humanas directas fuera de
  Claude Code** (respuesta a la pregunta abierta 3) — alcance ya aceptado
  desde ADR-002, no es una regresión de este ADR.
- **La promoción de ADR sigue siendo manual** (respuesta a la pregunta
  abierta 4) — se acepta como costo conocido y deliberado; si en el futuro
  se automatiza más el `pkf-implementer` y aparece fricción real repetida
  sobre ese paso específico, se debe revisar con su propia entrada en
  `docs/friction-log.md` antes de construir `tools/promote_adr.py`.

**Pendiente para la implementación (no decidido aquí, corresponde a
`pkf-implementer` y luego a `pkf-auditor`):** una vez implementado, correr
`python tools/check_refs.py`; verificar manualmente que un `git mv` de
prueba de `DRAFT-*.md` a `ADR-0XX-*.md` no se bloquea (criterio de
aceptación de la spec); marcar como resuelta (con fecha y referencia a este
ADR/implementación, sin borrar el contenido) la entrada de
`docs/friction-log.md` del 2026-07-07 sobre este mismo tema; documentar
`tools/add_business_rule.py` en `docs/orquestacion-claude-code.md` con el
mismo nivel de detalle que las demás piezas del pipeline.

## Referencias

- `specs/hook-proteccion-bash.md` — spec de origen de esta propuesta.
- `docs/friction-log.md`, entrada 2026-07-07 ("La protección de archivos
  (hook `PreToolUse`) no cubre `Bash`") — fricción que motiva este ADR.
- ADR-002 — Orquestación de PKF con hooks y subagentes; fija
  `protect_files.py`, la convención `DRAFT-<slug>.md` →
  `ADR-0XX-<slug>.md`, y ya anotaba "Bloquear también `Bash`" como
  alternativa descartada "por ahora" — este ADR es esa revisión.
- `.claude/hooks/protect_files.py` — hook existente sobre `Edit`/`Write`,
  fuente de `PROTECTED_PATTERNS` y del estilo de mensaje de error que este
  ADR reutiliza para `Bash`.
- `docs/business-rules.md` — RN-001, RN-002, RN-003, y el formato ("Formato
  de una regla de negocio") que `tools/add_business_rule.py` debe respetar.
- `docs/CONVENTIONS.md` — formato de RN y de nombres de archivo ADR/DRAFT.
- `docs/orquestacion-claude-code.md`, sección 4 (por qué `DRAFT-<slug>.md`
  y no dos carpetas) y sección 5 ("Siguientes pasos sugeridos", donde ya se
  anotaba un hook `PreToolUse` sobre `Bash` como paso futuro).
