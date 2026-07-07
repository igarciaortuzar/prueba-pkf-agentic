# Spec: modelo-datos-motor-validacion

## Contexto

Este proyecto es la demo/piloto del framework PKF con Claude Code (hooks +
subagentes), usando como caso de negocio real el "Sistema de Validación
Preventiva y Libro de Clases Digital" para la cuenta CODELCO de una OTIC.

ADR-003 (`docs/adr/ADR-003-hosting-y-persistencia-turso.md`, aceptada) ya
decidió el motor de base de datos: **Turso (libSQL)**, mismo dialecto SQL
que SQLite, hosteado junto con la app en Streamlit Community Cloud, con
concurrencia real esperada de **máximo 5 usuarios simultáneos**. Este spec
asume ese motor como dado y diseña el modelo de datos y el motor de
validación *sobre* libSQL.

El spec anterior (`specs/hosting-y-persistencia-turso.md`) dejó
explícitamente fuera de su alcance el modelo de datos completo y el motor
de validación de asistencia; este spec cubre esa parte pendiente.

Una primera versión de este spec dejó 15 preguntas abiertas (10 de modelo de
datos, 5 de reglas de validación). El dueño del proyecto resolvió
explícitamente las 4 más consecuentes para el diseño del esquema (ver
"Decisiones tomadas" más abajo); el resto se resuelve aquí con criterio
técnico razonable, documentando cada supuesto para que sea fácil de corregir
si no calza con la realidad operativa.

## Objetivo

Definir el modelo de datos (entidades, campos, relaciones) y formalizar las
tres reglas del motor de validación preventiva, sin ambigüedades, para que
puedan implementarse sobre Turso/libSQL sin descubrir vacíos a mitad de la
construcción.

## Decisiones tomadas (dueño del proyecto, 2026-07-07)

1. **Horarios:** se reemplaza el texto libre `modulo_horario` por
   `hora_inicio` / `hora_fin` explícitas por sesión de asistencia. No se
   introduce catálogo de turnos/módulos por ahora.
2. **Cálculo de horas del artículo (Regla B):** a nivel de curso completo,
   no por participante individual.
3. **Choque de horarios (Regla A):** alerta en tiempo real, no bloqueante.
   El coordinador decide cómo resolverlo; no impide seguir registrando
   asistencia.
4. **Calce de participantes vs. SC (Regla C):** se mantiene la lista
   completa de RUT esperados por SC (no solo un conteo), para poder
   identificar exactamente quién es "extra".

## Alcance

### Modelo de datos

Esquema resuelto, incorporando las decisiones anteriores y las brechas
detectadas en la primera versión del spec:

```sql
CREATE TABLE articulos (
    codigo_articulo TEXT PRIMARY KEY,
    nombre_curso TEXT NOT NULL,
    horas_obligatorias INTEGER NOT NULL
    -- Renombrado desde "horas_teoricas": se asume que representa el total
    -- de horas exigidas para cubrir el articulo (Regla B), sin distinguir
    -- componente teorico/practico. Si GPS distingue ambos por separado,
    -- hay que revisar este supuesto.
);

CREATE TABLE cursos (
    id_curso INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_articulo TEXT NOT NULL REFERENCES articulos(codigo_articulo),
    numero_sc TEXT,                      -- NULL si aun no existe SC (flujo borde, fuera de alcance)
    numero_otc TEXT NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    nombre_relator TEXT NOT NULL,
    correo_relator TEXT NOT NULL,
    minutos_colacion INTEGER NOT NULL DEFAULT 60,
    -- Default asumido (60 min); editable por curso. Ajustar el default si
    -- no corresponde a la realidad operativa real.
    estado TEXT NOT NULL DEFAULT 'Borrador'
        CHECK (estado IN (
            'Borrador',
            'En Curso',
            'Pendiente Cierre',
            'Pendiente Regularizacion SC',
            'Cerrado'
        )),
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    creado_por TEXT NOT NULL,
    actualizado_en TEXT,
    actualizado_por TEXT
);

CREATE TABLE participantes (
    rut_participante TEXT PRIMARY KEY,
    -- Formato canonico: sin puntos, con guion, digito verificador en
    -- mayuscula (ej. "12345678-9", "9876543-K"). Normalizar en la capa de
    -- aplicacion antes de insertar/consultar.
    id_sap INTEGER,
    -- Nullable: ya no se exige a participantes de origen 'Contratista'.
    origen TEXT NOT NULL CHECK(origen IN ('Codelco', 'Contratista')),
    nombre_completo TEXT NOT NULL,
    correo_institucional TEXT,
    division TEXT NOT NULL,
    -- Limitacion aceptada: se guarda como atributo de la persona (valor
    -- mas reciente), no por curso/momento. Si un participante cambia de
    -- division entre cursos, se pierde ese historial. Revisar si reporting
    -- futuro lo necesita.
    CHECK (origen != 'Codelco' OR id_sap IS NOT NULL)
);

CREATE TABLE asistencias (
    id_asistencia INTEGER PRIMARY KEY AUTOINCREMENT,
    id_curso INTEGER NOT NULL REFERENCES cursos(id_curso),
    rut_participante TEXT NOT NULL REFERENCES participantes(rut_participante),
    fecha_clase DATE NOT NULL,
    hora_inicio TEXT NOT NULL,   -- formato 'HH:MM', hora local
    hora_fin TEXT NOT NULL,
    estado_asistencia TEXT NOT NULL CHECK(estado_asistencia IN ('Presente', 'Ausente')),
    origen_registro TEXT NOT NULL CHECK(origen_registro IN (
        'Excel_PokaYoke', 'CSV_Teams', 'QR_Autoregistro', 'Manual'
    )),
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    creado_por TEXT NOT NULL,
    UNIQUE (id_curso, rut_participante, fecha_clase, hora_inicio)
);

-- Nueva entidad: lista de RUT esperados por SC (decision del dueño:
-- roster completo, no solo un conteo). Carga manual del coordinador OTIC
-- al vincular la SC al curso (ver "Preguntas abiertas" -> resuelta).
CREATE TABLE sc_participantes_esperados (
    numero_sc TEXT NOT NULL,
    rut_participante TEXT NOT NULL,
    cargado_en TEXT NOT NULL DEFAULT (datetime('now')),
    cargado_por TEXT NOT NULL,
    PRIMARY KEY (numero_sc, rut_participante)
);
```

**Limitaciones aceptadas (no bloquean este spec, quedan documentadas):**

- `division` en `participantes` no lleva historial por curso — se acepta
  como simplificación; revisar si se necesita en un spec futuro de
  reporting.
- No se modela una entidad "OTEC"/empresa todavía (sigue fuera de alcance,
  ver más abajo), pese a que ahora existe `sc_participantes_esperados`
  cuyo origen de carga también convendría auditar. Se anota como candidato
  fuerte para el siguiente spec.
- `horas_obligatorias` asume que no hay componente teórico/práctico
  separado. Si GPS lo distingue, este campo debe revisarse.

### Motor de validación preventiva

Tres reglas, con enunciado final y momento de ejecución ya resueltos:

**Regla A — Choque de horarios.** Alerta en tiempo real (no bloqueante) al
registrar una asistencia: mismo `rut_participante`, misma `fecha_clase`,
rango `[hora_inicio, hora_fin)` que se solapa con otro registro de otro
curso. Dos sesiones adyacentes que comparten exactamente el límite (una
termina a las 12:00, otra empieza a las 12:00) **no** se consideran
solapadas (intervalo semi-abierto). Solo puede detectar choques contra
otros cursos ya registrados en este sistema — no hay visibilidad de
actividades externas no registradas; esta es una limitación de los datos
disponibles, no algo que la regla pueda resolver.

**Regla B — Cobertura de horas del artículo.** Al intentar cerrar un curso
(no en tiempo real): la suma de `(hora_fin - hora_inicio)` de todas sus
sesiones, menos `minutos_colacion` por sesión, debe ser mayor o igual a
`horas_obligatorias` del `codigo_articulo` asociado. Cálculo a nivel de
curso completo, no por participante. Si no se cubre, el cierre queda
bloqueado.

**Regla C — Calce de participantes reales vs. SC.** Al intentar cerrar un
curso: si existe al menos un `rut_participante` con asistencia registrada
(`Presente` o `Ausente`) que no figura en `sc_participantes_esperados` para
el `numero_sc` del curso, el curso pasa a estado
`'Pendiente Regularizacion SC'`. Si `numero_sc` es `NULL` (curso sin SC
previa), el curso **no puede alcanzar el estado `'Cerrado'`** — queda
detenido en `'Pendiente Cierre'` hasta que se vincule una SC. Al vincularla
(acción del flujo borde "curso sin SC previa", fuera de alcance aquí), se
cargan los RUT esperados en `sc_participantes_esperados` y recién ahí se
evalúa la Regla C (y retroactivamente la Regla A, tal como describe el
documento original para ese flujo). Esta resolución es provisional: el
diseño completo de "vincular SC" queda para el spec de ese flujo borde,
pero ya fija el comportamiento mínimo esperado.

**Carga de `sc_participantes_esperados`:** manual, por el coordinador OTIC,
al momento de asociar/vincular la SC al curso (ya sea al crear el curso con
SC ya emitida, o al ejecutar "Vincular SC" en el flujo borde). No hay
ingestión automática desde ningún sistema de CODELCO en este spec.

**Concurrencia:** dado que la Regla A es una alerta no bloqueante, una
condición de carrera entre dos inserciones casi simultáneas (máximo 5
usuarios concurrentes) en el peor caso produce una alerta no disparada en el
momento exacto, no corrupción de datos ni un cierre incorrecto — se acepta
como riesgo de baja severidad, sin mitigación especial en este spec.

## Fuera de alcance

- Diseño del Excel protegido poka-yoke para captura offline.
- Importación y procesamiento de CSV de asistencia de MS Teams.
- Flujos borde: curso sin SC previa (incluye definir cómo interactúa con la
  Regla C), carga retroactiva de asistencia por lotes.
- Generación de PDF (libro de clases u otro reporte).
- Gestión de usuarios y roles granular (ya cubierta a nivel de decisión por
  ADR-003: contraseña compartida).
- Definición de la entidad "OTEC"/empresa como modelo de acceso o
  reporting — candidato fuerte para el siguiente spec dado que ahora existe
  `sc_participantes_esperados` sin dueño claro de su carga.
- Migración de datos existentes, si los hubiera.
- Implementación técnica del motor de validación (triggers de base de datos
  vs. lógica de aplicación) — queda para `pkf-architect`/`pkf-implementer`,
  respetando que Turso/libSQL soporta SQL estándar y transacciones.

## Preguntas abiertas

Todas las preguntas de la versión anterior de este spec quedaron resueltas
(ver "Decisiones tomadas", las notas junto a cada campo/regla, y la
resolución de la Regla C sobre `numero_sc IS NULL` y la carga de
`sc_participantes_esperados`, arriba). No quedan preguntas abiertas
bloqueantes para este spec. El único punto marcado explícitamente como
"provisional" (el comportamiento exacto de "vincular SC") se confirma o
ajusta cuando se escriba el spec del flujo borde "curso sin SC previa".

## Reglas de negocio (aprobadas: RN-001, RN-002, RN-003)

Estas tres reglas fueron candidatas directas a `docs/business-rules.md`
según `docs/CONVENTIONS.md`. El dueño del proyecto las aprobó explícitamente
(2026-07-07); quedaron creadas como **RN-001**, **RN-002** y **RN-003** en
`docs/business-rules.md`, con el mismo enunciado redactado aquí. Se
mantiene el texto en este spec como referencia de origen.

### RN-001 (Candidata A) — Detección de choque de horarios

**Regla:** Un participante (RUT) no puede tener asistencia registrada en dos
cursos distintos, en la misma fecha, con rangos horarios `[hora_inicio,
hora_fin)` que se solapen (los límites exactos compartidos entre sesiones
adyacentes no cuentan como solape). La detección ocurre en tiempo real al
registrar la asistencia, como alerta no bloqueante — no impide continuar,
el coordinador decide cómo resolverlo. Solo se detectan choques contra
cursos registrados en este mismo sistema.

**Origen:** Documento de propuesta técnica original del sistema (motor de
validación preventiva de asistencia).

### RN-002 (Candidata B) — Cobertura de horas obligatorias del artículo

**Regla:** Antes de permitir el cierre de un curso, la suma de horas netas
de sus sesiones (duración de cada sesión menos los minutos de colación
configurados) debe ser mayor o igual a las horas obligatorias definidas por
el código de artículo (GPS) asociado. El cálculo es a nivel del curso
completo, no por participante individual. Si no se cubre, el cierre del
curso queda bloqueado.

**Origen:** Documento de propuesta técnica original del sistema (motor de
validación preventiva de asistencia).

### RN-003 (Candidata C) — Calce de participantes reales vs. Solicitud de Compra

**Regla:** Por cada Solicitud de Compra (SC) se mantiene la lista de RUT de
participantes esperados. Al intentar cerrar un curso, si existe al menos un
participante con asistencia registrada (presente o ausente) cuyo RUT no
figura en la lista de RUT esperados de la SC asociada al curso, el curso se
marca automáticamente en estado `"Pendiente Regularizacion SC"`. Si el
curso no tiene SC asociada, esta regla queda pendiente de definir junto con
el flujo borde de "curso sin SC previa" (fuera de alcance de este spec).

**Origen:** Documento de propuesta técnica original del sistema (motor de
validación preventiva de asistencia).

## Criterios de aceptación

- El esquema de tablas anterior (o uno que `pkf-architect` derive de él,
  documentando cualquier cambio) cubre las tres reglas candidatas (A, B, C)
  con datos ya almacenados, sin suposiciones externas: existe
  `sc_participantes_esperados` para el calce de RUT, y existen
  `hora_inicio`/`hora_fin` para calcular solapes y horas netas.
- Las tres reglas candidatas tienen enunciado final sin ambigüedad (ya
  resuelto en este spec) y ese es el texto que se usa si/cuando el dueño
  del proyecto las apruebe como RN-xxx.
- El diseño no depende de ninguna capacidad que Turso/libSQL no soporte
  (coherente con ADR-003); si se usan triggers de base de datos para alguna
  validación, se confirma que libSQL los soporta con el comportamiento
  esperado.
- Queda explícito, en el ADR o documento que resulte, que la Regla A se
  valida en tiempo real (alerta no bloqueante) y las Reglas B y C se
  validan al intentar cerrar un curso.
- Este spec no decide el Excel poka-yoke, el import de CSV de Teams, los
  flujos borde de SC ausente o carga retroactiva, la entidad OTEC, ni la
  generación de PDF — quedan explícitamente fuera de alcance, para specs
  futuros.
