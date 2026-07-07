#!/usr/bin/env python3
"""Lista compartida de patrones de rutas protegidas de PKF.

Fuente unica de verdad para `protect_files.py` (hook `PreToolUse` sobre
`Edit`/`Write`) y `protect_bash_writes.py` (hook `PreToolUse` sobre `Bash`).
Antes de ADR-006 esta lista vivia duplicada solo en `protect_files.py`;
ADR-006 seccion "Cambios de configuracion necesarios" recomienda
extraerla a un modulo compartido para no desincronizar los dos hooks si se
agrega un archivo protegido nuevo (riesgo ya anotado como "vigilado" en
ADR-002).

AJUSTA esta lista si extiendes el guardrail a mas archivos (ver
docs/friction-log.md, entrada 2026-07-03).
"""

PROTECTED_PATTERNS = [
    r"(^|/)AGENTS\.md$",
    r"(^|/)docs/business-rules\.md$",
    r"(^|/)docs/adr/ADR-\d{3}-.*\.md$",
    # Agrega aqui otros archivos protegidos segun vayas extendiendo el guardrail
    # (esta era la idea abierta en el friction-log de PKF).
]
