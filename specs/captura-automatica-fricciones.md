# Spec: captura-automatica-fricciones

## Contexto

`docs/friction-log.md` (entrada del 2026-07-07, "La captura de fricciones
depende de que el dueño del proyecto se acuerde de preguntar, no ocurre por
iniciativa propia") documenta que, durante toda una sesión de trabajo
(instalación del kit PKF, specs, ADRs, RN, implementación de scaffold),
ninguna fricción se registró por iniciativa de la IA. Las tres entradas de
fricción de ese mismo día solo existen porque el dueño del proyecto preguntó
explícitamente, al cierre de la sesión, "¿encontraste alguna fricción?" — y
una de esas tres era un bug real (permisos faltantes en `pkf-spec`) que se
habría perdido de no preguntar.

Esto contradice el principio fundacional de PKF: "el framework crece por
extracción" (`docs/friction-log.md`, encabezado), que presupone que la
extracción ocurre como parte natural del flujo de trabajo, no como algo que
depende de que un humano se acuerde de pedirla explícitamente al final.

La propia entrada de fricción ya deja anotadas tres soluciones candidatas,
ninguna decidida ni evaluada en profundidad:

1. Agregar un paso explícito en `AGENTS.md` (sección 6 o una nueva) que pida
   proponer candidatas a friction-log antes de cerrar cualquier tarea no
   trivial.
2. Un hook `Stop` de Claude Code que recuerde, al final de cada turno de
   respuesta del agente principal, revisar si hubo fricciones sin registrar.
3. Aceptar que sea un hábito humano deliberado, documentado explícitamente
   en vez de dejarlo implícito.

La propia entrada de fricción ya advierte que implementar cualquiera de
estas opciones (en particular un hook nuevo) es un cambio estructural (P3 de
`AGENTS.md`: nueva integración) y requiere su propio spec/ADR antes de tocar
código — que es justamente lo que esta spec inicia.

## Objetivo

Definir un mecanismo (o combinación de mecanismos) que reduzca la
dependencia de que el dueño del proyecto recuerde preguntar por fricciones,
sin asumir en silencio cuál de las opciones ya barajadas es la correcta —
eso lo decide el dueño del proyecto a partir de esta spec y del ADR que
la siga.

## Alcance

- Evaluar críticamente, con criterio explícito y trade-offs a la vista, las
  tres soluciones candidatas ya anotadas en `docs/friction-log.md`
  (2026-07-07), incluyendo la posibilidad de combinarlas.
- Dejar explícita la tensión técnica real de los hooks `Stop` y `SessionEnd`
  de Claude Code (ver "Preguntas abiertas") como insumo para que
  `pkf-architect` diseñe el mecanismo concreto.
- Si el mecanismo elegido incluye escribir directamente en
  `docs/friction-log.md` (a diferencia de solo recordar), dejar constancia
  de que ese archivo **no** está en `PROTECTED_PATTERNS` de
  `.claude/hooks/protect_files.py` hoy — cualquier agente ya puede escribir
  ahí sin bloqueo técnico. Evaluar si eso debe seguir así (facilita la
  extracción) o si conviene un guardrail distinto (por ejemplo, exigir que
  las entradas queden marcadas como "propuesta, no confirmada" hasta
  revisión humana).
- Definir qué se entiende operacionalmente por "tarea no trivial" a efectos
  de este mecanismo, apoyándose en la tabla de sección 4 de `AGENTS.md`
  (Trivial / Normal / Estructural) en vez de crear un criterio paralelo.
- El resultado de esta spec es la base para que `pkf-architect` registre un
  ADR con la decisión concreta (qué mecanismo(s), con qué configuración).

## Fuera de alcance

- Modificar `AGENTS.md` directamente (este documento solo puede proponerlo;
  cualquier cambio real requiere instrucción explícita del dueño y mostrar
  el diff antes de guardar, por P2 y sección 5 de `AGENTS.md`).
- Escribir o modificar hooks de Claude Code (`.claude/hooks/`,
  `.claude/settings.json`) — eso es implementación, corresponde a
  `pkf-implementer` una vez exista un ADR aceptado.
- Rediseñar los hooks `SessionStart`, `PreToolUse` o `PostToolUse` ya
  existentes en este repo, salvo que el mecanismo elegido requiera
  extender `PROTECTED_PATTERNS` para `docs/friction-log.md` (ver Alcance).
- Automatizar la generación del *contenido* de una entrada de fricción
  (redacción, clasificación de severidad) — el foco es que la propuesta
  ocurra, no reemplazar el juicio humano sobre si una fricción es real o
  merece quedar registrada.
- Cualquier mecanismo que dependa de servicios externos nuevos (fuera de
  las capacidades nativas de Claude Code ya usadas en este repo).
- Resolver fricciones ya cerradas o no relacionadas (por ejemplo las otras
  entradas de `docs/friction-log.md` del 2026-07-07) — esta spec atiende
  únicamente la entrada "La captura de fricciones depende de que el dueño
  del proyecto se acuerde de preguntar".

## Preguntas abiertas

- **Tensión técnica real de los hooks disponibles** (dato dado, no
  investigar): un hook `Stop` puro solo puede ejecutar un script — por
  ejemplo, inyectar un texto de recordatorio que el agente lea recién en su
  *siguiente* turno. No puede hacer que la IA "reflexione y proponga" en el
  momento exacto sin que exista un turno de conversación posterior que lea
  ese recordatorio. Y si se dispara en **cada** turno (no solo al cierre de
  tareas significativas), puede volverse ruidoso o molesto en una
  conversación larga. Un hook `SessionEnd`, en cambio, corre después de que
  la sesión ya terminó — no hay más inferencia posible en ese momento, así
  que no puede pedirle nada a la IA cuando se dispara. Ningún hook, por sí
  solo, resuelve el problema de raíz sin ese matiz.
- **¿Cuál opción evaluar primero?** No la decido — la decide el dueño del
  proyecto — pero dejo mi lectura crítica de cada una como insumo:
  - *Opción 1 (paso explícito en `AGENTS.md`)*: barata, sin infraestructura
    nueva, accionable de inmediato. Su debilidad es que depende de que el
    propio agente principal recuerde seguir esa instrucción en el momento
    de cerrar la tarea — es decir, sigue dependiendo de la "memoria" del
    agente, aunque ahora esté escrita como regla en vez de como pregunta
    ad-hoc del humano. Es un avance real (de "nadie lo pide" a "está
    escrito que hay que pedirlo"), pero no es un guardraíl duro.
  - *Opción 2 (hook `Stop`)*: agrega un guardraíl técnico real (no depende
    de que el agente "se acuerde" de una instrucción en prosa), pero tiene
    las limitaciones técnicas señaladas arriba: solo puede recordar en el
    turno siguiente, y disparar en cada turno puede ser ruidoso. Requeriría
    diseño adicional para acotar cuándo dispara (¿solo si hubo ediciones a
    `specs/`, `docs/adr/`, `docs/business-rules.md` en la sesión? ¿solo una
    vez por sesión en vez de por turno?) — ese diseño queda para
    `pkf-architect`, no para esta spec.
  - *Opción 3 (hábito humano documentado)*: formaliza por escrito lo que ya
    es la situación actual (el dueño del proyecto pregunta). Mi lectura es
    que esto no resuelve la fricción de raíz, porque la fricción original
    es exactamente "depende de que el humano se acuerde" — documentarlo
    explícitamente ayuda a que no dependa de la memoria de una sola
    persona si se hace un checklist de cierre de sesión, pero sigue siendo
    un control humano, no técnico.
  - **Mi recomendación, sujeta a decisión del dueño del proyecto:** evaluar
    primero una combinación de Opción 1 (barata, inmediata, sin
    dependencias nuevas) con una versión acotada de la Opción 2 (hook
    `Stop` que no dispare en cada turno, sino condicionado a alguna señal
    de que hubo trabajo no trivial en la sesión — por ejemplo, ediciones a
    `specs/`, `docs/adr/DRAFT-*.md` o `docs/business-rules.md`). La Opción
    3 sola la veo como el statu quo que ya produjo la fricción, más que
    como una solución nueva.
- Si se opta por un hook `Stop`, ¿debería condicionarse a qué herramientas o
  archivos se tocaron en la sesión (para evitar ruido en turnos triviales),
  o dispararse siempre y aceptar el costo de ruido a cambio de simplicidad
  de implementación?
- ¿El mecanismo elegido debe aplicar solo al agente principal (orquestador)
  o también a los subagentes PKF (`pkf-spec`, `pkf-architect`,
  `pkf-implementer`, `pkf-auditor`), dado que cada uno corre en su propio
  contexto/turno?
- ¿"Tarea no trivial" se define igual que en la tabla de sección 4 de
  `AGENTS.md` (Normal / Estructural), o necesita un criterio propio para
  este mecanismo?
- ¿Vale la pena, en el mismo esfuerzo, agregar `docs/friction-log.md` a
  `PROTECTED_PATTERNS` de `protect_files.py` (para que una entrada nueva
  pase por revisión humana antes de quedar escrita), o eso iría en contra
  del objetivo de bajar la fricción de captura?

## Criterios de aceptación

- Existe un ADR (a redactar por `pkf-architect`) que documenta cuál
  mecanismo (o combinación) se adopta, con las alternativas descartadas y
  por qué, apoyándose en la evaluación de esta spec.
- El ADR resuelve explícitamente la tensión técnica de los hooks `Stop` /
  `SessionEnd` señalada arriba — no la deja pendiente ni la ignora.
- El mecanismo elegido no requiere que el dueño del proyecto pregunte
  explícitamente "¿encontraste alguna fricción?" al final de una sesión
  para que una fricción real tenga oportunidad de registrarse.
- Si el mecanismo implica un hook nuevo, queda documentado en
  `docs/orquestacion-claude-code.md` (siguiendo el patrón ya usado para
  `SessionStart`/`PreToolUse`/`PostToolUse`) y reflejado en
  `.claude/settings.json`.
- Si el mecanismo implica un cambio a `AGENTS.md`, se implementa mostrando
  el diff completo antes de guardar (regla de sección 5 de `AGENTS.md`,
  originada en la entrada de fricción del 2026-07-03) y con instrucción
  explícita del dueño del proyecto.
- La entrada de fricción del 2026-07-07 que motiva esta spec queda
  actualizada (no borrada, marcada) indicando qué solución se adoptó y
  cuándo, siguiendo la convención de "marcar, no eliminar" de
  `docs/CONVENTIONS.md`.
- Esta spec no decide por sí sola cuál de las tres opciones (o combinación)
  se implementa — deja la evaluación y la recomendación por escrito, y la
  decisión final queda para el dueño del proyecto vía el ADR.
