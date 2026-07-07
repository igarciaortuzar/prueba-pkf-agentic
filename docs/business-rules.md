# Reglas de negocio

> Registro único de reglas de negocio del proyecto. Ver formato en `CONVENTIONS.md`.
> Este archivo solo se modifica con instrucción explícita del dueño del proyecto (P2 de AGENTS.md).

**Próximo número disponible:** 004

---

### RN-001 — Detección de choque de horarios de participantes

**Estado:** vigente
**Regla:** Un participante (identificado por RUT) no puede tener asistencia
registrada en dos cursos distintos, en la misma fecha, con rangos horarios
`[hora_inicio, hora_fin)` que se solapen. Sesiones adyacentes que comparten
exactamente el límite de hora (una termina a las 12:00, otra empieza a las
12:00) no se consideran solapadas. La detección es una alerta en tiempo
real al registrar la asistencia, no bloqueante: no impide continuar, el
coordinador decide cómo resolverla. Solo se detectan choques contra cursos
ya registrados en este sistema.
**Origen:** Propuesta técnica del Sistema de Validación Preventiva y Libro
de Clases Digital (cuenta CODELCO), formalizada en
`specs/modelo-datos-motor-validacion.md`.
**Historial:**
- 2026-07-07 — creada.

---

### RN-002 — Cobertura de horas obligatorias del artículo

**Estado:** vigente
**Regla:** Antes de permitir el cierre de un curso, la suma de horas netas
de sus sesiones (duración de cada sesión menos los minutos de colación
configurados) debe ser mayor o igual a las horas obligatorias definidas por
el código de artículo (GPS) asociado al curso. El cálculo se realiza a
nivel del curso completo, no por participante individual. Si no se cubre,
el cierre del curso queda bloqueado.
**Origen:** Propuesta técnica del Sistema de Validación Preventiva y Libro
de Clases Digital (cuenta CODELCO), formalizada en
`specs/modelo-datos-motor-validacion.md`.
**Historial:**
- 2026-07-07 — creada.

---

### RN-003 — Calce de participantes reales vs. Solicitud de Compra

**Estado:** vigente
**Regla:** Por cada Solicitud de Compra (SC) se mantiene la lista de RUT de
participantes esperados. Al intentar cerrar un curso, si existe al menos un
participante con asistencia registrada (presente o ausente) cuyo RUT no
figura en la lista de RUT esperados de la SC asociada, el curso se marca
automáticamente en estado "Pendiente Regularizacion SC". Si el curso no
tiene SC asociada, no puede alcanzar el estado "Cerrado" hasta que se
vincule una SC (comportamiento provisional, sujeto a confirmación en el
spec del flujo "curso sin SC previa").
**Origen:** Propuesta técnica del Sistema de Validación Preventiva y Libro
de Clases Digital (cuenta CODELCO), formalizada en
`specs/modelo-datos-motor-validacion.md`.
**Historial:**
- 2026-07-07 — creada.

---

<!-- PLANTILLA de regla — copiar y completar:

### RN-XXX — Título corto de la regla

**Estado:** vigente
**Regla:** enunciado preciso, verificable, sin ambigüedad.
**Origen:** contrato / cliente / normativa / decisión interna (referencia).
**Historial:**
- AAAA-MM-DD — creada.

-->
