# ADR-XXX — Hosting en Streamlit Community Cloud con persistencia en Turso (libSQL)

**Fecha:** 2026-07-07
**Estado:** propuesta

## Contexto

El "Sistema de Validación Preventiva y Libro de Clases Digital" (caso de
negocio de la cuenta CODELCO de una OTIC) se desarrolla sin equipo de TI
interno, sin presupuesto para licencias por usuario, por una sola persona
apoyada en IA, con concurrencia real esperada de máximo 5 usuarios
simultáneos.

La propuesta técnica original planteaba Streamlit + SQLite local, sin
contemplar backup. Se detectaron dos riesgos: (1) Streamlit Community Cloud
tiene disco efímero — un SQLite local ahí puede perderse en cualquier
redeploy o reinicio; (2) no había backup del archivo, y el sistema activa
pagos a proveedores (pérdida de datos = impacto financiero directo). Estos
riesgos ya fueron discutidos y resueltos por el dueño del proyecto antes de
este spec: se reemplaza SQLite local por Turso.

## Decisión

Hostear la aplicación en **Streamlit Community Cloud** (gratuito, sin
dependencia de IT interno) y usar **Turso (libSQL)** como motor de base de
datos —servicio gestionado externo, mismo dialecto SQL que SQLite— en vez de
un archivo SQLite local, para que la persistencia no dependa del disco
efímero de Streamlit Cloud y se apoye en el backup/replicación gestionado
que Turso incluye en su tier gratuito. El acceso de las OTECs externas
(pocas, conocidas) se protege con **autenticación por contraseña compartida**
a nivel de aplicación, sin cuentas individuales gestionadas por IT ni
licenciamiento por usuario. Las credenciales de conexión a Turso y la
contraseña compartida se guardan en Streamlit secrets (mecanismo nativo de
Streamlit Community Cloud para configuración sensible), sin implementar aquí
el detalle del mecanismo.

El "sleep" de Streamlit Community Cloud por inactividad se acepta como
limitación conocida de UX (demora de arranque de ~30-60s para el primer
visitante tras un período sin uso), no como riesgo de datos: la persistencia
vive en Turso, independiente del estado del contenedor de la app. No se
agrega infraestructura para evitarlo ahora; queda como mitigación de reserva
un ping periódico vía GitHub Actions si en la práctica molesta.

## Alternativas consideradas

- **SQLite local en Streamlit Community Cloud** — descartada: el disco es
  efímero, cualquier redeploy o reinicio puede perder el archivo completo;
  no resuelve el riesgo que originó este spec y dejaría sin protección los
  pagos a proveedores que dependen de esos datos.
- **Otras bases de datos gestionadas (Postgres gestionado tipo Supabase/
  Neon/Railway, MySQL gestionado, Firebase/Firestore)** — descartadas por
  esta iteración: habrían resuelto igualmente el problema de persistencia,
  pero introducen un dialecto SQL distinto (o no-SQL) al de la propuesta
  original, más piezas de infraestructura y/o curva de adopción para una
  sola persona manteniendo el proyecto, sin beneficio adicional claro sobre
  Turso para esta escala (máximo 5 usuarios concurrentes). Turso, al ser
  libSQL (fork de SQLite), permite reusar directamente el modelo de datos
  pensado para SQLite y minimiza el cambio respecto a la propuesta original.
- **Backup propio programado (script + storage externo) sobre SQLite
  local** — descartada: agrega mantenimiento operativo (programar, correr,
  verificar, alertar sobre fallos de backup) que no puede sostener un equipo
  de una persona; Turso resuelve esto como servicio ya incluido en su tier
  gratuito.
- **Cuentas individuales por OTEC gestionadas por IT** — descartada: no hay
  equipo de IT interno y las OTECs son externas; una contraseña compartida
  a nivel de aplicación cubre el requisito de acceso protegido sin ese
  costo de gestión.

## Consecuencias

**Se gana:** persistencia de datos independiente del ciclo de vida del
contenedor de Streamlit Cloud; backup y replicación sin script propio que
mantener; acceso externo protegido sin licenciamiento por usuario ni
dependencia de IT; migración de la propuesta original de bajo costo (mismo
dialecto SQL que SQLite).

**Se pierde / se acepta:** dependencia de un servicio externo (Turso) fuera
del control directo del proyecto; el "sleep" de Streamlit Community Cloud
introduce una demora ocasional de UX (~30-60s) en el primer acceso tras
inactividad, aceptada explícitamente como no-riesgo de datos; la
autenticación por contraseña compartida es un mecanismo simple, no un
control de acceso granular por OTEC ni una gestión de usuarios auditable.

**Riesgos vigilados / preguntas abiertas sin resolver en este ADR** (quedan
explícitas porque el spec no las cerró; deben resolverse antes o durante la
implementación):

- No se ha validado con volumen real si los límites del tier gratuito de
  Turso (almacenamiento, filas leídas/escritas por mes, número de bases de
  datos) alcanzan para el uso esperado de la cuenta CODELCO.
- No está definido si la contraseña compartida es única y global para
  todas las OTECs o una distinta por OTEC.
- No está definido dónde y cómo se gestiona y rota la contraseña
  compartida (más allá de "vive en Streamlit secrets"), ni quién es
  responsable de esa rotación.
- No se ha validado si existe algún requisito contractual de CODELCO/OTIC
  sobre residencia o soberanía de los datos que la región/proveedor de
  Turso deba cumplir.
- Riesgo de cambio de pricing del tier gratuito de Turso a futuro: no
  bloquea esta decisión, pero se registra como riesgo a vigilar; el mismo
  dialecto SQL (libSQL/SQLite) facilita una migración si fuera necesario.

**Responsabilidades:** Turso es responsable de backup y replicación de los
datos. El equipo del proyecto sigue siendo responsable de las credenciales
de conexión, la rotación de la contraseña compartida y el monitoreo básico
de disponibilidad de la app.

## Referencias

- `specs/hosting-y-persistencia-turso.md`
- ADR-001 — Adoptar PKF v0.1 como estructura del proyecto (contexto de
  framework, sin conflicto con esta decisión).
- ADR-002 — Orquestación de PKF con hooks y subagentes (define que los
  ADR en borrador viven como `DRAFT-<slug>.md` hasta promoción humana).
