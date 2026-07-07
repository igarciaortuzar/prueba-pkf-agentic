# Sistema de Validación Preventiva y Libro de Clases Digital (Cuenta CODELCO)

Aplicación web para la gestión de capacitación de la cuenta CODELCO de una
OTIC: mueve la validación de datos de asistencia (choques de horario, calce
de horas por artículo, calce de participantes vs. Solicitud de Compra) del
cierre administrativo reactivo al momento de la captura, para reducir el
retraso actual de ~20 días hábiles entre fin de curso y pago/registro en
GPS. Ver `docs/vision-general-sistema.md` para el estado completo: qué está
decidido y qué falta por definir.

## Cómo está organizado

Este proyecto usa **PKF v0.1** (Project Knowledge Framework), una estructura mínima
para que tanto personas como IAs puedan trabajar en el repositorio sin depender
de contexto externo.

| Si buscas... | Ve a... |
|---|---|
| Entender el proyecto | Este README |
| Colaborar con una IA | `AGENTS.md` (reglas de colaboración) |
| Las reglas de negocio | `docs/business-rules.md` |
| Por qué se decidió algo | `docs/adr/` |
| Convenciones de docs | `docs/CONVENTIONS.md` |
| Cómo Claude Code aplica PKF automáticamente | `docs/orquestacion-claude-code.md` |
| El estado completo del sistema (decidido / pendiente) | `docs/vision-general-sistema.md` |
| Qué se está construyendo ahora mismo | `queue/_queue.json` |

## Cómo empezar

Existe un scaffold inicial (hosting, conexión a base de datos y gate de
autenticación — ver ADR-003). El esquema de datos del dominio y el motor de
validación (ADR-004) todavía no están implementados (ver
`queue/_queue.json` para el estado exacto de cada pieza).

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml  # opcional en dev
streamlit run app.py
```

Sin `TURSO_DATABASE_URL` configurado, la app usa automáticamente un archivo
libSQL local (`local.db`) en vez de Turso — ver `app/db.py`.

```bash
python -m pytest
```

## Validar consistencia

```bash
python tools/check_refs.py
```

Verifica que toda referencia a reglas de negocio (RN-xxx) y decisiones (ADR-xxx)
apunte a algo que existe. Correr antes de cada commit relevante.
