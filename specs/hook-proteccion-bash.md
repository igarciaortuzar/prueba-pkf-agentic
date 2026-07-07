# Spec: hook-proteccion-bash

## Contexto

`docs/friction-log.md` (entrada 2026-07-07, "La protección de archivos (hook
`PreToolUse`) no cubre `Bash`") registra que `.claude/hooks/protect_files.py`
solo intercepta las herramientas `Edit` y `Write` (ver `.claude/settings.json`,
matcher `"Edit|Write"`). ADR-002 dejó esto como decisión de diseño deliberada:
`Bash` queda sin proteger a propósito para permitir el `mv` humano de
promoción de ADR (`docs/adr/DRAFT-<slug>.md` → `docs/adr/ADR-0XX-<slug>.md`,
ver ADR-002 sección "Alternativas consideradas" y
`docs/orquestacion-claude-code.md` sección 4).

Pero en la práctica esa misma puerta abierta se usó, en la misma sesión, para
un caso más amplio de lo previsto: crear RN-001, RN-002 y RN-003 directamente
en `docs/business-rules.md` vía un heredoc de `Bash`, evitando por completo
el guardrail que `protect_files.py` aplica a `Edit`/`Write` sobre ese mismo
archivo. La única barrera real en ese camino fue que el agente decidiera
seguir la disciplina de "mostrar diff antes de guardar" — exactamente el
problema que motivó crear los hooks de `PreToolUse` en primer lugar (ver
`docs/friction-log.md`, entrada 2026-07-03, y ADR-002, sección "Contexto").

`docs/orquestacion-claude-code.md` sección 5 ("Siguientes pasos sugeridos")
ya anotaba un hook `PreToolUse` sobre `Bash` como paso futuro, aunque
enfocado originalmente en comandos destructivos (`rm -rf`, `git push
--force`), no en escritura directa a archivos protegidos.

## Objetivo

Cerrar (o acotar deliberadamente, si no se cierra del todo) el hueco por el
cual `Bash` puede escribir contenido directamente en archivos protegidos de
PKF (`AGENTS.md`, `docs/business-rules.md`, ADRs ya aceptados) sin pasar por
el guardrail que ya existe para `Edit`/`Write`, sin romper el flujo legítimo
de promoción de ADR (`mv`/renombrado de `DRAFT-<slug>.md` a
`ADR-0XX-<slug>.md`) que ADR-002 protegió explícitamente.

## Alcance

- Diseñar (a nivel de spec/arquitectura, no de código — eso le corresponde a
  `pkf-architect`) un mecanismo que reduzca la posibilidad de que `Bash`
  escriba contenido nuevo directamente sobre las rutas ya listadas en
  `PROTECTED_PATTERNS` de `protect_files.py` (`AGENTS.md`,
  `docs/business-rules.md`, `docs/adr/ADR-\d{3}-*.md`).
- Definir explícitamente qué operaciones de `Bash` sobre esas rutas (o sobre
  `docs/adr/DRAFT-*.md`) deben seguir permitidas sin fricción — como mínimo,
  el `mv`/`git mv` de promoción de ADR descrito en
  `docs/orquestacion-claude-code.md` sección 4.
- Definir un mecanismo legítimo y auditable para que el dueño del proyecto,
  con instrucción explícita, pueda seguir creando/modificando RN nuevas y
  otro contenido protegido sin depender de que un hook heurístico lo deje
  pasar "por accidente".
- Revisar si el cambio implica tocar `.claude/settings.json` (agregar `Bash`
  al matcher de `PreToolUse`) y/o `.claude/hooks/protect_files.py`, y si hace
  falta un script nuevo en `tools/` (evaluado como opción en "Preguntas
  abiertas", no decidido aquí).

## Fuera de alcance

- Bloquear comandos destructivos de `Bash` (`rm -rf`, `git push --force`,
  etc.) — es una idea distinta, ya anotada por separado en
  `docs/orquestacion-claude-code.md` sección 5, y no forma parte de esta
  fricción concreta.
- Cambiar la convención `DRAFT-<slug>.md` → `ADR-0XX-<slug>.md` en sí misma,
  o la numeración correlativa de ADRs — eso es una decisión ya tomada en
  ADR-002 y no está en discusión aquí.
- Distinguir "qué subagente" está pidiendo el cambio dentro del hook —
  ADR-002 ya documentó explícitamente que el JSON de entrada del hook no
  trae esa información de forma confiable, y esta spec no propone revisar
  ese supuesto.
- Implementar el mecanismo elegido — corresponde a `pkf-implementer` una vez
  que exista un ADR aceptado que resuelva las preguntas abiertas de abajo.
- Resolver la fricción separada del 2026-07-07 sobre captura de fricciones
  por iniciativa propia (última entrada del friction-log) — no tiene
  relación con esta.

## Preguntas abiertas

1. **Tensión central a resolver por `pkf-architect`, no por esta spec:**
   cualquier hook `PreToolUse` sobre `Bash` que intente bloquear escrituras a
   rutas protegidas corre el riesgo real de bloquear también el `mv`/`git mv`
   legítimo de promoción de ADR que ADR-002 protegió deliberadamente. Hay que
   decidir cómo el hook distingue, con una señal confiable (no una
   heurística frágil de texto):
   - "renombrar/mover un archivo `DRAFT-<slug>.md` existente a
     `ADR-0XX-<slug>.md`" → debe seguir permitido sin fricción.
   - "escribir contenido nuevo directamente en un ADR ya aceptado, en
     `docs/business-rules.md` o en `AGENTS.md`" (vía heredoc, `sed -i`,
     `echo >>`, `cat >`, edición por editor de línea de comandos, etc.) →
     debe bloquearse.

2. **¿Vale la pena una heurística de detección de comandos de `Bash`, o es
   la alternativa equivocada?** Evaluación crítica que debe hacer
   `pkf-architect` explícitamente en el ADR, no asumirse:
   - Una heurística basada en regex sobre el string del comando (buscar
     `>`, `>>`, `sed -i`, nombres de archivo protegidos, etc.) nunca va a
     ser 100% confiable. Falsos negativos son inevitables (hay
     infinitas formas de escribir un archivo desde `Bash`: `python -c
     "..."`, `tee`, `dd`, un script intermedio, variables de entorno que
     ofuscan el path, etc.). Falsos positivos también: un `git mv` legítimo
     de promoción de ADR, o un `cat docs/business-rules.md` de solo lectura,
     podrían coincidir con un patrón mal diseñado y bloquear trabajo válido.
   - Alternativa a evaluar seriamente: **dejar `Bash` sin bloqueo directo por
     patrón de comando, pero proveer un camino legítimo y auditable para las
     excepciones ya conocidas** (el `mv`/`git mv` de promoción de ADR, y la
     creación de RN nuevas con instrucción explícita del dueño) mediante un
     script controlado en `tools/` — por ejemplo `tools/add_business_rule.py`
     — que el propio hook pudiera reconocer como excepción explícita (por
     ejemplo, si el hook sí interceptara `Bash`, permitiendo comandos que
     invoquen exactamente ese script y bloqueando el resto de escrituras
     directas por patrón de archivo). Esto no resuelve el problema general
     de "cualquier comando de Bash puede escribir cualquier archivo", pero sí
     resuelve el caso concreto observado (heredoc directo a
     `business-rules.md`) sin la carga de mantener una heurística de regex
     sobre shell arbitrario.
   - Un punto intermedio: mantener `Bash` fuera del `PreToolUse` de bloqueo
     duro (como hoy), pero agregar una capa de detección más débil —por
     ejemplo un hook `PostToolUse` sobre `Bash` que, si detecta que el
     comando tocó una ruta protegida, lo señale fuerte (no bloqueante, dado
     que ya corrió) para que quede evidencia en la sesión y se refuerce la
     disciplina de revisar el diff. Esto no es un guardrail duro, así que
     hay que ser honesto en el ADR sobre que no resuelve el problema de raíz
     si el objetivo es un bloqueo real como el que ya existe para
     `Edit`/`Write`.

3. Si se opta por el script en `tools/` como camino legítimo: ¿reemplaza
   por completo la posibilidad de editar `business-rules.md`/`AGENTS.md`
   manualmente fuera de Claude Code (edición humana directa con un editor de
   texto, fuera de la sesión), o esa vía sigue existiendo en paralelo? Nada
   en el hook de `Edit`/`Write` ni en un eventual hook de `Bash` puede
   bloquear una edición humana hecha fuera de Claude Code — vale la pena que
   el ADR sea explícito sobre que el guardrail cubre agentes dentro de la
   sesión de Claude Code, no ediciones humanas directas al filesystem.

4. ¿El mismo mecanismo elegido debe aplicarse también a la creación de ADRs
   nuevos vía `tools/` (por ejemplo, un `tools/promote_adr.py` que haga el
   `mv` y el cambio de `Estado:` en un solo paso auditable), o se prefiere
   mantener ese paso como un gesto manual humano (`mv` a mano) precisamente
   porque es el caso que ADR-002 quiso dejar fuera de cualquier
   automatización? Esta spec no lo decide; lo deja explícito para que
   `pkf-architect` lo resuelva con una decisión registrada.

5. Si se agrega un hook `PreToolUse` sobre `Bash`, ¿cómo evitar que el
   matcher `"Bash"` en `.claude/settings.json` interfiera con comandos de
   `Bash` legítimos y frecuentes que no tienen nada que ver con archivos
   protegidos (correr tests, `git status`, `python tools/check_refs.py`,
   etc.)? Cualquier diseño debe minimizar falsos positivos sobre el uso
   normal de `Bash`, no solo los casos de archivos protegidos.

## Criterios de aceptación

- El ADR resultante (a cargo de `pkf-architect`) responde explícitamente,
  con una decisión registrada y su alternativa descartada, a la pregunta
  abierta 2 (heurística de regex sobre `Bash` vs. camino legítimo auditable
  vía `tools/`), incluyendo el trade-off de falsos positivos/negativos
  descrito arriba — no debe asumirse en silencio.
- El mecanismo elegido, una vez implementado, **no bloquea** el flujo
  documentado en `docs/orquestacion-claude-code.md` sección 4 (renombrar
  `docs/adr/DRAFT-<slug>.md` a `docs/adr/ADR-0XX-<slug>.md` como parte de la
  promoción humana de un ADR). Esto se verifica con una prueba manual
  concreta: promover un ADR de prueba en `DRAFT-*.md` a `ADR-0XX-*.md` vía
  `Bash`/`git mv` después de implementado el cambio, y confirmar que no se
  bloquea.
- El mecanismo elegido **sí impide o señala de forma verificable** el caso
  concreto observado en esta sesión: escribir contenido nuevo en
  `docs/business-rules.md` (o `AGENTS.md`, o un ADR ya aceptado) vía un
  heredoc u otro comando de `Bash` que evite `Edit`/`Write`. Si la decisión
  final es "señalar, no bloquear" (opción más débil de la pregunta 2), el
  ADR debe decirlo explícitamente y justificar por qué es aceptable dado el
  objetivo original de tener un guardrail "real, no una sugerencia" (ADR-002,
  sección Contexto).
- Si se crea `tools/add_business_rule.py` (o script equivalente), queda
  documentado en `docs/orquestacion-claude-code.md` con el mismo nivel de
  detalle que las demás piezas del pipeline, y referenciado desde
  `docs/friction-log.md` como la solución aplicada a la entrada del
  2026-07-07.
- `python tools/check_refs.py` sigue pasando sin errores tras el cambio.
- La entrada de `docs/friction-log.md` del 2026-07-07 ("La protección de
  archivos (hook `PreToolUse`) no cubre `Bash`") queda marcada como resuelta
  (con fecha y referencia al ADR/implementación), no borrada, siguiendo P5 de
  `AGENTS.md`.
- Ningún archivo protegido (`AGENTS.md`, `docs/business-rules.md`, ADRs
  aceptados) se edita directamente como parte de esta spec ni de las fases
  siguientes sin pasar por el proceso ya establecido (diff mostrado, o el
  mecanismo legítimo nuevo que se decida).
