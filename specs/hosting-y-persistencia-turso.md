# Spec: hosting-y-persistencia-turso

## Contexto

Este proyecto es una demo/piloto del framework PKF con Claude Code (hooks +
subagentes), usando como caso de negocio real una propuesta de "Sistema de
Validación Preventiva y Libro de Clases Digital" para la cuenta CODELCO de
una OTIC.

La propuesta técnica original planteaba: app web en Streamlit, base de datos
SQLite local, generación de Excel protegido (poka-yoke) para captura offline,
importación de CSV de asistencia de MS Teams, y un motor de validación
(choques de horario, calce de horas por artículo, calce de participantes vs.
Solicitud de Compra).

Restricciones reales del proyecto: sin soporte de equipo de TI interno, sin
presupuesto para licencias por usuario, desarrollo ejecutado por una sola
persona apoyada en IA. Concurrencia real esperada: máximo 5 usuarios
simultáneos (no "decenas" como decía el documento original).

Se detectaron dos riesgos en la propuesta original, ya discutidos y resueltos
por el dueño del proyecto:

1. Streamlit Community Cloud (la opción obvia de hosting gratis, sin IT)
   tiene disco efímero: un archivo SQLite local ahí se puede perder en
   cualquier redeploy o reinicio.
2. La propuesta original no contemplaba backup del archivo SQLite, y el
   sistema activa pagos a proveedores (impacto financiero si se pierde el
   dato).

Decisión ya tomada (instrucción explícita del dueño, no se reabre en este
spec): reemplazar el archivo SQLite local por Turso (libSQL, mismo dialecto
SQL, servicio gestionado) como base de datos, hosteada junto con la app en
Streamlit Community Cloud. Turso resuelve ambos riesgos a la vez: da
persistencia real (no depende del disco efímero de Streamlit Cloud) y ya
incluye replicación/backup gestionado en su tier gratuito. El acceso de las
OTECs externas (pocas, conocidas) se resuelve con autenticación simple por
contraseña compartida a nivel de aplicación (no licencias por usuario).

## Objetivo

Definir y dejar documentada la arquitectura de hosting y persistencia de
datos de la aplicación (dónde vive la app, qué motor de base de datos se usa,
cómo se protege el acceso externo) de forma que resuelva los riesgos de
pérdida de datos de la propuesta original, sin equipo de TI y sin costos de
licenciamiento por usuario.

## Alcance

- Hosting de la aplicación: Streamlit Community Cloud (gratuito, sin
  dependencia de IT interno).
- Motor de base de datos: Turso (libSQL) como reemplazo del SQLite local,
  como servicio gestionado externo a Streamlit Cloud.
- Persistencia y backup: apoyarse en la replicación/backup gestionado que
  incluye el tier gratuito de Turso, evitando programar y mantener un script
  de backup propio.
- Acceso externo de las OTECs: autenticación simple por contraseña
  compartida a nivel de aplicación (no cuentas individuales gestionadas por
  IT, no licenciamiento por usuario).
- Dejar explícito, para que quede en el ADR correspondiente, qué alternativas
  se consideraron (SQLite local, otras DB gestionadas) y por qué se
  descartaron.
- Definir a alto nivel dónde y cómo se guardan las credenciales de conexión
  a Turso y la contraseña compartida (ej. Streamlit secrets), sin
  implementar el mecanismo.

## Fuera de alcance

- Diseño completo del motor de validación de asistencia (choques de horario,
  calce de horas por artículo, calce de participantes vs. Solicitud de
  Compra).
- Diseño del Excel protegido poka-yoke para captura offline.
- Importación y procesamiento de CSV de asistencia de MS Teams.
- Modelo de datos / esquema de tablas de la aplicación.
- Gestión de usuarios y roles granular (más allá de la contraseña
  compartida a nivel de aplicación).
- Migración de datos existentes, si los hubiera.
- Aspectos comerciales o contractuales con la OTIC/CODELCO (costos, SLA
  contractual, aprobación de proveedor).
- Monitoreo, alertas u observabilidad operacional de la app en producción.

## Preguntas abiertas

- ¿Cuáles son los límites exactos del tier gratuito de Turso (almacenamiento,
  filas leídas/escritas por mes, número de bases de datos) y son suficientes
  para el volumen real esperado de la cuenta CODELCO? No se ha validado con
  datos reales.
- ¿La contraseña compartida es única y global para todas las OTECs, o una
  por OTEC? No quedó especificado en la conversación previa.
- ¿Dónde y cómo se gestiona/rota la contraseña compartida (Streamlit
  secrets, variable de entorno, proceso de cambio periódico, quién es
  responsable)?
- ~~Streamlit Community Cloud "duerme" las apps por inactividad...~~
  **Resuelta:** el sleep afecta solo al contenedor de la app (demora de
  arranque de ~30-60s para el primer visitante tras un período sin uso), no
  a los datos — la persistencia ya vive en Turso, independiente del estado
  de Streamlit Cloud. Dado el patrón de uso esperado (varias visitas por
  semana mientras hay cursos activos), no representa un riesgo de
  integridad de pagos ni de cierre de cursos, solo una demora ocasional de
  UX. No se agrega infraestructura para esto ahora. Mitigación de reserva,
  gratuita y sin dependencias nuevas, si en la práctica molesta: un ping
  periódico vía GitHub Actions programado que visite la URL cada par de
  días para evitar que la app entre en sleep.
- ¿Hay algún requisito contractual de CODELCO/OTIC sobre residencia de datos
  (soberanía de datos, país del proveedor cloud) que Turso deba cumplir?
- ¿Qué pasa si el pricing gratuito de Turso cambia en el futuro? No bloquea
  esta decisión, pero conviene que el ADR registre el riesgo y un plan de
  salida (mismo dialecto SQL facilita migrar si fuera necesario).

## Criterios de aceptación

- Existe un ADR (a redactar por `pkf-architect`) que documenta la decisión
  de usar Turso + Streamlit Community Cloud, las alternativas consideradas
  (SQLite local, otras DB gestionadas) y por qué se descartaron.
- El diseño resultante no depende de disco local persistente en ningún
  componente crítico; queda explícito que Streamlit Community Cloud es
  efímero y no debe usarse para guardar estado.
- El acceso externo de las OTECs queda protegido por al menos un mecanismo
  de autenticación (contraseña compartida), sin requerir licencias por
  usuario ni cuentas individuales gestionadas por IT.
- La solución no introduce la necesidad de un script de backup mantenido por
  el equipo del proyecto; se apoya explícitamente en el backup/replicación
  gestionado de Turso.
- Queda documentado qué es responsabilidad del proveedor (Turso: backup,
  replicación) y qué sigue siendo responsabilidad del equipo del proyecto
  (credenciales, rotación de contraseña, monitoreo básico de disponibilidad).
- Este spec no toma decisiones sobre el motor de validación de asistencia,
  el Excel poka-yoke, ni la importación de CSV de Teams — quedan
  explícitamente fuera de alcance, para specs futuros.
