# AGENTS.md

> Instrucciones para cualquier IA (Claude, ChatGPT, Gemini, Copilot u otra) que colabore
> en este proyecto. Este archivo sigue el estándar AGENTS.md (https://agents.md).
> Léelo completo antes de hacer cualquier cambio.

## 1. Qué es este proyecto

**Nombre:** Sistema de Validación Preventiva y Libro de Clases Digital (Cuenta CODELCO)
**Propósito:** Mover la validación de datos de asistencia de capacitación
(choques de horario, calce de horas por artículo, calce de participantes
vs. Solicitud de Compra) del cierre administrativo reactivo a la captura
preventiva, para reducir el retraso actual de ~20 días hábiles entre fin
de curso y pago/registro en GPS.
**Estado:** exploración (arquitectura y modelo de datos decididos vía ADR;
sin código de aplicación implementado todavía — ver `queue/_queue.json`)
**Stack principal:** Python, Streamlit (hosting: Streamlit Community
Cloud), Turso (libSQL)

## 2. Mapa del repositorio

| Ruta | Qué contiene | ¿La IA puede modificarla? |
|---|---|---|
| `README.md` | Presentación para humanos nuevos | Sí, si cambia el alcance |
| `AGENTS.md` | Este archivo | Solo con instrucción explícita del dueño |
| `docs/` | Documentación viva del proyecto | Sí, siguiendo `docs/CONVENTIONS.md` |
| `docs/business-rules.md` | Registro de reglas de negocio (RN-xxx) | Solo con instrucción explícita |
| `docs/adr/` | Decisiones de arquitectura (ADR-xxx) | Sí, agregando; nunca editando ADRs aceptados |
| `src/` (o equivalente) | Código fuente | Sí |
| `tools/` | Scripts de validación del propio framework | Sí |

## 3. Principios de colaboración

Ordenados por prioridad; ante conflicto, gana el de número menor.

- **P1 — Divergencia:** si docs y código (o dos documentos) se contradicen, detente, repórtalo, propón cuál versión parece correcta y espera confirmación. No elijas una versión en silencio.
- **P2 — RN protegidas:** las reglas de `docs/business-rules.md` (RN-xxx) solo se crean o modifican con instrucción explícita del dueño. Si una tarea implica cambiar una RN, decláralo antes de tocar código.
- **P3 — Decisiones quedan escritas:** toda decisión técnica no trivial (librería, estructura de datos, integración externa, trade-off de diseño) se registra como ADR en `docs/adr/` usando la plantilla, como parte del entregable.
- **P4 — Docs y código viajan juntos:** un cambio que altera comportamiento, estructura o interfaz actualiza en el mismo commit los documentos afectados.
- **P5 — No se borra historia:** lo obsoleto se marca (fecha + reemplazo), nunca se elimina. Los ADR aceptados no se editan; uno nuevo reemplaza al anterior.
- **P6 — Referencias estables:** cita RN-xxx/ADR-xxx por su ID real, nunca por paráfrasis. Corre `python tools/check_refs.py` antes de cerrar una tarea que agregó o referenció IDs, y corrige lo que reporte.

## 4. Rutas según tamaño del cambio

| Tipo | Ejemplos | Proceso |
|---|---|---|
| **Trivial** | Typo, formato, comentario, rename local | Hazlo directo, sin ceremonia. |
| **Normal** | Nueva función, fix de bug, ajuste de lógica | Código + docs afectados juntos (P4). |
| **Estructural** | Nueva entidad, cambio de RN, nueva integración, decisión de arquitectura | Primero ADR o actualización de RN, luego implementación. |

Si dudas entre dos categorías, asume la más exigente.

## 5. Qué nunca debe hacer una IA en este proyecto

- Inventar el contenido de un archivo que no pudo leer.
- Modificar `AGENTS.md`, `docs/business-rules.md` o ADRs aceptados sin instrucción explícita.
- Resolver una inconsistencia eligiendo en silencio una versión (viola P1).
- Eliminar información histórica en vez de marcarla obsoleta (viola P5).
- Introducir dependencias, servicios externos o credenciales sin declararlo.
- Guardar cambios a `AGENTS.md` sin mostrarlos antes como diff, incluso con instrucción explícita, dado su rol de gobernar el resto del proyecto.

## 6. Cómo empezar una sesión de trabajo

1. Lee este archivo, luego `README.md`.
2. Lee lo relevante de `docs/` (índice en `docs/CONVENTIONS.md`).
3. Recién entonces, toca código.

## 7. Antes de cerrar una tarea Normal o Estructural

Antes de dar por cerrada cualquier tarea clasificada como **Normal** o
**Estructural** (tabla de la sección 4), cualquier agente (el
orquestador principal o un subagente PKF) debe revisar si encontró
alguna fricción real durante el trabajo — algo que no encontró donde
esperaba, una convención que estorbó, un permiso faltante, una
ambigüedad que tuvo que resolver por su cuenta, etc. — y proponerla
explícitamente como candidata a `docs/friction-log.md`, en vez de
esperar a que el dueño del proyecto pregunte.

Esto no reemplaza el juicio humano: el agente **nunca escribe una
entrada nueva en `docs/friction-log.md` en silencio**. Antes de
documentar (o de decidir no documentar) una fricción candidata, debe
anunciarla explícitamente al dueño del proyecto como parte de su
respuesta — mostrando qué encontró y cuál es su intención (documentarla
o no, y con qué severidad) — y esperar confirmación o instrucción antes
de escribir la entrada. Si la tarea no tuvo ninguna fricción real que
valga la pena anotar, basta con decirlo explícitamente ("no encontré
fricciones dignas de registrar en esta tarea") en vez de omitir el paso
sin mencionarlo.

Si trabajas en Claude Code, un hook `Stop`
(`.claude/hooks/stop_friction_reminder.py`, ver
`docs/orquestacion-claude-code.md`) refuerza este paso técnicamente
cuando detecta ediciones a `specs/`, `docs/adr/DRAFT-*.md` o
`docs/business-rules.md` durante la sesión — pero el hook solo puede
recordarlo en el turno siguiente, no reemplaza este paso ni te exime de
seguirlo cuando trabajas fuera de una sesión con hooks activos.

---

*Este proyecto usa PKF (Project Knowledge Framework) v0.1. El framework crece por
extracción: si una sesión revela fricción real, anótala en `docs/friction-log.md`
en vez de improvisar una solución estructural.*
