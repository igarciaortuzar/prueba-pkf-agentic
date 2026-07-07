# ADR-004 — Modelo de datos y motor de validación preventiva sobre Turso/libSQL

**Fecha:** 2026-07-07
**Estado:** aceptada

## Contexto

ADR-003 (aceptada) ya fijó el motor de datos (Turso/libSQL, mismo dialecto
que SQLite) y el entorno de despliegue (Streamlit Community Cloud, máximo 5
usuarios concurrentes) para el "Sistema de Validación Preventiva y Libro de
Clases Digital" de la cuenta CODELCO. Ese ADR dejó explícitamente fuera de
su alcance el modelo de datos completo y el motor de validación de
asistencia.

`specs/modelo-datos-motor-validacion.md` cierra esa brecha: define el
esquema de tablas y formaliza tres reglas de negocio, ya aprobadas por el
dueño del proyecto como **RN-001**, **RN-002** y **RN-003** en
`docs/business-rules.md`, con el mismo enunciado exacto que aparece en el
spec. El spec resuelve todas sus preguntas abiertas previas mediante
decisiones explícitas del dueño (2026-07-07): horarios explícitos por
sesión (`hora_inicio`/`hora_fin`), cálculo de horas del artículo a nivel de
curso completo, choque de horario como alerta no bloqueante, y roster
completo (no solo conteo) de RUT esperados por Solicitud de Compra (SC).

Verificación de consistencia: se revisaron ADR-001, ADR-002, ADR-003 y
RN-001/RN-002/RN-003 contra el spec. No se detectó ninguna contradicción —
el spec asume Turso/libSQL y el límite de 5 usuarios concurrentes tal como
los fijó ADR-003, y el enunciado de las tres reglas en el spec es idéntico,
palabra por palabra en lo sustantivo, al que ya quedó registrado en
`docs/business-rules.md`. Esta propuesta de ADR cubre la decisión de diseño
que el spec dejó pendiente para `pkf-architect`: dónde vive la lógica del
motor de validación (capa de aplicación Python vs. triggers de libSQL), no
la implementación en código.

## Decisión

**Esquema de tablas** (tal como quedó resuelto en el spec, sin cambios):

- `articulos(codigo_articulo PK, nombre_curso, horas_obligatorias)` — total
  de horas exigidas por artículo GPS, sin distinguir componente
  teórico/práctico.
- `cursos(id_curso PK, codigo_articulo FK, numero_sc NULL-able, numero_otc,
  fecha_inicio, fecha_fin, nombre_relator, correo_relator,
  minutos_colacion DEFAULT 60, estado CHECK IN ('Borrador', 'En Curso',
  'Pendiente Cierre', 'Pendiente Regularizacion SC', 'Cerrado'),
  auditoría de creación/actualización)`.
- `participantes(rut_participante PK, id_sap NULL-able, origen CHECK IN
  ('Codelco','Contratista'), nombre_completo, correo_institucional,
  division)` con CHECK de que `id_sap` es obligatorio solo para origen
  `'Codelco'`.
- `asistencias(id_asistencia PK, id_curso FK, rut_participante FK,
  fecha_clase, hora_inicio, hora_fin, estado_asistencia CHECK IN
  ('Presente','Ausente'), origen_registro, auditoría de creación,
  UNIQUE(id_curso, rut_participante, fecha_clase, hora_inicio))`.
- `sc_participantes_esperados(numero_sc, rut_participante, cargado_en,
  cargado_por, PK compuesta)` — roster completo de RUT esperados por SC,
  carga manual del coordinador OTIC al vincular la SC al curso.

**Motor de validación — dónde vive la lógica:** las tres reglas (RN-001,
RN-002, RN-003) se implementan **en la capa de aplicación Python**
(el backend de la app Streamlit), no como triggers de libSQL ni como CHECK
constraints adicionales a nivel de esquema (más allá de los CHECK de enum
ya listados arriba, que son integridad estructural, no reglas de negocio).

- **RN-001 (choque de horarios):** función de la capa de aplicación,
  ejecutada de forma síncrona inmediatamente después (o antes) de insertar
  un registro en `asistencias`, dentro de la misma acción de usuario. La
  función consulta `asistencias` por `rut_participante` + `fecha_clase` a
  través de todos los cursos, evalúa el solape de intervalos semi-abiertos
  `[hora_inicio, hora_fin)`, y si hay solape **muestra una alerta en la UI
  sin bloquear el insert ni la continuación del flujo**. No hay trigger ni
  constraint de base de datos involucrado: es una consulta de lectura, sin
  efecto en la escritura.
- **RN-002 (cobertura de horas) y RN-003 (calce de participantes vs. SC):**
  función de la capa de aplicación invocada exclusivamente por la acción
  explícita "Cerrar curso". Antes de escribir el nuevo `estado` en
  `cursos`, la función, dentro de una única transacción (`BEGIN...COMMIT`
  de libSQL):
  1. Calcula la suma de minutos netos de todas las sesiones del curso
     (`hora_fin - hora_inicio` menos `minutos_colacion` por sesión) y la
     compara contra `horas_obligatorias` del artículo asociado (RN-002). Si
     no se cubre, el cierre se rechaza y el curso permanece en su estado
     previo — bloqueo aplicado en código de aplicación, no por un CHECK ni
     trigger de libSQL.
  2. Si `numero_sc` del curso es `NULL`, el cierre se rechaza (el curso no
     puede alcanzar `'Cerrado'`, permanece en `'Pendiente Cierre'`) —
     comportamiento provisional según el spec, sujeto a confirmación en el
     spec del flujo borde "curso sin SC previa".
  3. Si `numero_sc` existe, compara el conjunto de `rut_participante` con
     asistencia registrada contra `sc_participantes_esperados` para ese
     `numero_sc` (RN-003). Si hay al menos un RUT no esperado, la
     transacción escribe `estado = 'Pendiente Regularizacion SC'` en vez de
     `'Cerrado'`.
  Todo el cálculo, las comparaciones y la decisión de qué `estado` escribir
  viven en Python; libSQL solo ejecuta las lecturas y el `UPDATE` final
  dentro de la transacción.

Esta decisión es coherente con ADR-003: no introduce ninguna dependencia de
capacidades de libSQL más allá de SQL estándar y transacciones (no se usan
triggers), preservando la portabilidad que motivó elegir libSQL sobre otras
bases (mismo dialecto que SQLite, migración de bajo costo si fuera
necesario).

## Alternativas consideradas

- **Triggers de libSQL para las tres reglas** — descartada como mecanismo
  principal: los triggers de SQLite/libSQL pueden ejecutar SQL pero no
  producir directamente una alerta no bloqueante en la UI (RN-001) sin
  tablas auxiliares adicionales; para RN-002/RN-003, un trigger `BEFORE
  UPDATE` que rechace la transición de `estado` es viable, pero acopla la
  regla de negocio a sintaxis específica de libSQL, dificulta las pruebas
  unitarias (requeriría un harness de base de datos en vez de tests de
  Python puro) y concentra la lógica de negocio en un lugar que un
  proyecto de una sola persona mantiene con más fricción que código Python
  versionado y revisable. Se prioriza la opción más simple de mantener
  dado el contexto de ADR-001 (equipo de una persona apoyada en IA).
- **CHECK constraint a nivel de esquema para bloquear el `UPDATE` de
  `estado` a `'Cerrado'`** — descartada: un CHECK de SQLite/libSQL no puede
  expresar una agregación (`SUM`) ni un `JOIN` contra otra tabla, que es
  justamente lo que requieren RN-002 y RN-003; sería necesario un trigger
  de todas formas, con las mismas desventajas del punto anterior.
- **Enforzar las tres reglas exclusivamente en la capa de aplicación,
  incluyendo bloqueo real del insert para RN-001 (en vez de alerta no
  bloqueante)** — descartada: contradice la decisión explícita del dueño
  del proyecto documentada en el spec ("Choque de horarios: alerta en
  tiempo real, no bloqueante. El coordinador decide cómo resolverlo").
- **Mantener el cálculo de horas del artículo (RN-002) por participante
  individual** — descartada: contradice la decisión explícita del dueño
  ("Cálculo de horas del artículo a nivel de curso completo, no por
  participante individual").
- **Guardar solo un conteo de participantes esperados por SC (en vez del
  roster completo de RUT)** — descartada: contradice la decisión explícita
  del dueño y no permitiría identificar exactamente quién es "extra", que
  es el motivo por el que existe la tabla `sc_participantes_esperados`.

## Consecuencias

**Se gana:** la lógica de negocio de las tres reglas queda en Python,
testeable con pruebas unitarias sin depender de un harness de base de
datos; se mantiene la portabilidad de libSQL/SQLite que motivó ADR-003 (sin
sintaxis de triggers específica de un proveedor); un solo lugar en el
código concentra las tres reglas, más fácil de mantener y de auditar para
un equipo de una persona.

**Se pierde / se acepta:**

- **Las reglas no se aplican a nivel de base de datos.** Si en el futuro
  se introduce un segundo camino de escritura a Turso que no pase por la
  app Streamlit (por ejemplo, un script de carga retroactiva de asistencia
  por lotes — mencionado en el spec como flujo borde fuera de alcance),
  RN-002 y RN-003 podrían violarse silenciosamente porque solo viven en el
  código de la app. Se acepta porque hoy la app Streamlit es el único
  cliente de escritura previsto; esta decisión debe revisarse cuando se
  diseñe ese flujo borde.
- **Riesgo de condición de carrera en RN-001, ya documentado en el spec
  como aceptado:** con máximo 5 usuarios concurrentes, dos inserciones casi
  simultáneas podrían no disparar la alerta en el momento exacto. No hay
  corrupción de datos ni cierre incorrecto — se acepta como riesgo de baja
  severidad, sin mitigación adicional en esta propuesta.
- **Limitación aceptada — historial de `division` no versionado:**
  `participantes.division` se guarda como atributo de la persona (valor
  más reciente), no por curso/momento. Si un participante cambia de
  división entre cursos, se pierde ese historial. Queda pendiente de
  revisión si un futuro spec de reporting lo necesita.
- **Limitación aceptada — entidad "OTEC" pendiente:** no se modela todavía
  una entidad "OTEC"/empresa, pese a que `sc_participantes_esperados` ya
  existe sin un dueño claro y auditable de su carga (más allá de
  `cargado_por`/`cargado_en` como campos planos). Se registra como
  candidato fuerte para el siguiente spec, tal como señala el spec de
  origen.
- **Provisional — comportamiento de cierre sin SC:** que un curso con
  `numero_sc IS NULL` quede detenido indefinidamente en
  `'Pendiente Cierre'` (sin poder alcanzar `'Cerrado'`) es el
  comportamiento mínimo fijado por RN-003 y el spec, pero está
  explícitamente marcado como provisional, pendiente de confirmación o
  ajuste cuando se escriba el spec del flujo borde "curso sin SC previa"
  (incluyendo cómo se cargan retroactivamente `sc_participantes_esperados`
  y cómo se reevalúan RN-001/RN-003 en ese momento).
- **`horas_obligatorias` asume un solo total sin componente
  teórico/práctico separado** — si el sistema GPS de CODELCO distingue
  ambos componentes, este campo y RN-002 deben revisarse.

## Referencias

- RN-001, RN-002, RN-003 — `docs/business-rules.md`.
- ADR-003 — Hosting en Streamlit Community Cloud con persistencia en Turso
  (libSQL); fija el motor de datos y el límite de 5 usuarios concurrentes
  que esta propuesta da por sentado.
- ADR-002 — Orquestación de PKF con hooks y subagentes; define que este
  documento vive como `DRAFT-<slug>.md` hasta promoción humana a
  `ADR-0XX-<slug>.md`.
- `specs/modelo-datos-motor-validacion.md` — spec de origen de esta
  propuesta.
