# Visión general: Sistema de Validación Preventiva y Libro de Clases Digital

> Este documento resume el estado del sistema en un solo lugar: el problema
> de negocio, qué arquitectura está decidida (con su ADR), y qué falta por
> definir. No es una decisión en sí — es un mapa de las decisiones ya
> tomadas en `docs/adr/` y `docs/business-rules.md`, para no depender de
> reconstruir el contexto desde una conversación. Actualízalo cuando se
> agregue un ADR o RN nuevo relevante al panorama general.
>
> La propuesta técnica original (documento externo del especialista de
> mejora continua) no se guarda tal cual en este repo — quedó parcialmente
> superada por decisiones posteriores (ver "Diferencias vs. la propuesta
> original" más abajo). Este documento es la versión vigente y procesada.

## El problema de negocio (vigente, no ha cambiado)

La cuenta CODELCO de una OTIC gestiona capacitación bajo "Cuenta 2" (fondos
directos de capacitación corporativa, fuera del flujo SENCE). El cierre
administrativo de un curso — tomar asistencia, validar contra la Solicitud
de Compra (SC), registrar en GPS (SAP SuccessFactors de CODELCO) y pagar al
proveedor (OTEC) — tarda en promedio **~20 días hábiles** desde que termina
el curso.

Causas identificadas en la propuesta original:

- Las reglas de validación de GPS (choques de horario, calce de horas,
  calce de participantes vs. SC) se revisan manualmente **al final** del
  proceso, no al momento de capturar los datos.
- Los relatores de las OTECs usan planillas de libro de clases
  desprotegidas, con riesgo de error humano en datos críticos (ej. nombre
  comercial del curso distinto al nombre oficial en GPS).
- Un equipo de 3 digitadoras revisa manualmente, celda por celda, antes de
  digitar en GPS para evitar rechazos.

Restricciones reales del proyecto (tampoco han cambiado): sin equipo de TI
interno asignado, sin presupuesto para licencias por usuario, desarrollo
ejecutado por una sola persona apoyada en IA.

## Qué está decidido (con ADR/RN)

| Decisión | Dónde está registrada |
|---|---|
| Hosting: Streamlit Community Cloud | ADR-003 |
| Persistencia: Turso (libSQL), no SQLite de archivo local | ADR-003 |
| Acceso externo de OTECs: contraseña compartida a nivel de app | ADR-003 |
| Esquema de tablas (`articulos`, `cursos`, `participantes`, `asistencias`, `sc_participantes_esperados`) | ADR-004 |
| El motor de validación vive en Python (capa de aplicación), no en triggers de libSQL | ADR-004 |
| RN-001 — Choque de horarios: alerta en tiempo real, no bloqueante | `docs/business-rules.md` |
| RN-002 — Cobertura de horas del artículo: cálculo por curso completo, bloquea el cierre | `docs/business-rules.md` |
| RN-003 — Calce de participantes vs. SC: roster completo de RUT esperados, marca `Pendiente Regularizacion SC` | `docs/business-rules.md` |

Riesgos vigilados, ya aceptados explícitamente (no bloquean nada, pero hay
que revisarlos en algún momento): límites reales del tier gratuito de
Turso, gestión/rotación de la contraseña compartida, requisitos de
residencia de datos de CODELCO/OTIC, historial de `division` no versionado
por participante, condición de carrera de baja severidad en RN-001 (ver
ADR-003 y ADR-004 para el detalle de cada uno).

## Qué falta por definir (sin spec ni ADR todavía)

Ninguno de estos puntos tiene una decisión de arquitectura tomada — quedan
explícitamente fuera de alcance de los specs existentes:

- **Captura offline:** diseño del Excel con cabecera protegida (poka-yoke)
  que el relator descarga/sube para registrar asistencia sin señal.
- **Importación de asistencia por streaming:** procesamiento del CSV nativo
  de MS Teams (extracción de correos institucionales, cálculo de minutos
  conectados, marca de asistencia automática).
- **Flujo "curso sin SC previa":** autoregistro por QR, y cómo se vincula
  la SC formal después (afecta directamente a RN-003 — ver el
  comportamiento provisional descrito en ADR-004).
- **Carga retroactiva por lotes:** importación masiva de cursos internos de
  CODELCO dictados por relatores de planta.
- **Entidad "OTEC"/empresa:** quién registró cada curso/asistencia y quién
  cargó cada roster de `sc_participantes_esperados` — señalado en ADR-004
  como candidato fuerte para el próximo spec.
- **Generación del libro de clases certificado en PDF**, con firmas de
  relator y OTEC.
- Gestión de usuarios más allá de la contraseña compartida (si algún día
  hiciera falta).

## Diferencias vs. la propuesta técnica original

La propuesta original de la que partió este proyecto planteaba algunas
cosas que **ya no aplican** tal cual, por decisiones tomadas durante el
diseño (ver ADR-003 y ADR-004 para el razonamiento completo):

- **Base de datos:** proponía SQLite como archivo local. Se decidió Turso
  (libSQL) en su lugar, porque Streamlit Community Cloud tiene disco
  efímero (un archivo local se puede perder en cualquier redeploy) y
  porque el sistema activa pagos a proveedores — no había backup
  contemplado originalmente.
- **Calce de participantes vs. SC:** proponía solo "contar" personas
  agregadas en caliente. Se decidió mantener la lista completa de RUT
  esperados por SC (`sc_participantes_esperados`), para poder identificar
  exactamente quién es "extra", no solo cuántos.
- **Concurrencia:** la propuesta hablaba de "decenas" de relatores
  simultáneos. El volumen real esperado es máximo 5 usuarios concurrentes
  — esto simplificó varias decisiones (ej. no hace falta una cola de
  escritura para SQLite/Turso).
- **Choque de horarios:** la propuesta no especificaba si era bloqueante o
  no. Se decidió que sea una alerta en tiempo real, no bloqueante — no
  impide seguir trabajando.

El resto de la propuesta original (flujos borde, Excel poka-yoke, CSV
Teams, generación de PDF) sigue vigente como dirección general, pero ninguna
de esas partes tiene todavía una decisión formal de arquitectura — ver
"Qué falta por definir" arriba.

## Cómo se construyó este documento

Este proyecto es también una demo del framework PKF orquestado con hooks y
subagentes de Claude Code (ver `docs/orquestacion-claude-code.md`). Cada
fila de la tabla de decisiones tomadas pasó por el pipeline
`pkf-spec` → `pkf-architect` → (aprobación humana) antes de registrarse
aquí. El estado de ejecución en tiempo real de cada item vive en
`queue/_queue.json`, no en este documento.
