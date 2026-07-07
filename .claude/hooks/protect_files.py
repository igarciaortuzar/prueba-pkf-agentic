#!/usr/bin/env python3
"""PreToolUse hook: bloquea Edit/Write sobre archivos protegidos de PKF.

Se dispara ANTES de que la herramienta corra. Si el path del archivo matchea
un patron protegido, sale con codigo 2: Claude Code cancela la accion y le
muestra el mensaje de stderr al agente como error. Esto es un bloqueo real
(no una sugerencia) -- funciona incluso en modo --dangerously-skip-permissions.

IMPORTANTE - decision de diseno (ver ADR-002 y docs/CONVENTIONS.md): este
hook NO distingue que subagente esta pidiendo el cambio (el JSON de entrada
no trae esa info de forma confiable), y este repo NO usa carpetas separadas
para ADRs en borrador vs aceptados -- usa una convencion de nombres:

  - docs/adr/DRAFT-<slug>.md       (NO protegido) -> el subagente architect
    escribe aqui libremente su propuesta (con "Estado: propuesta").
  - docs/adr/ADR-XXX-<slug>.md     (SI protegido) -> promover un ADR es un
    acto humano deliberado: renombrar el archivo de DRAFT-<slug>.md a
    ADR-0XX-<slug>.md (asignando el numero correlativo) y cambiar el campo
    "Estado:" a "aceptada". Ese renombrado/mv es lo que activa la proteccion,
    no algo que un agente decide por su cuenta.

AJUSTA la lista PROTECTED_PATTERNS en protected_patterns.py si extiendes el
guardrail a mas archivos (ver docs/friction-log.md, entrada 2026-07-03).

Nota (ADR-006): PROTECTED_PATTERNS vive en protected_patterns.py, modulo
compartido con .claude/hooks/protect_bash_writes.py, para no duplicar la
lista en dos archivos.
"""
import json
import re
import sys

from protected_patterns import PROTECTED_PATTERNS


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Si no logramos parsear el input, no bloqueamos por un problema nuestro.
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "") or ""

    for pattern in PROTECTED_PATTERNS:
        if re.search(pattern, file_path):
            print(
                f"[PKF] BLOQUEADO: '{file_path}' es un archivo protegido "
                f"(coincide con '{pattern}'). Este archivo requiere edicion "
                f"manual y revision humana del diff, no edicion directa por "
                f"un agente. Si el cambio es legitimo:\n"
                f"  - Para ADRs: trabaja el borrador en docs/adr/DRAFT-<slug>.md "
                f"y pide al humano que lo renombre a docs/adr/ADR-0XX-<slug>.md "
                f"con Estado: aceptada.\n"
                f"  - Para AGENTS.md/business-rules.md: edita el archivo tu "
                f"mismo fuera de este flujo, revisando el diff linea por linea.",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
