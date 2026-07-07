#!/usr/bin/env python3
"""Stop hook: recuerda proponer fricciones candidatas cuando la sesion toco
archivos de alto impacto para PKF (specs/, un DRAFT de ADR o
docs/business-rules.md).

Ver ADR-005 (docs/adr/ADR-005-captura-automatica-fricciones.md) para el
diseno completo y su razonamiento, y AGENTS.md seccion 7 (pendiente de
aprobacion humana al momento de escribir este hook) para el paso que este
hook refuerza tecnicamente.

Contrato del evento Stop (JSON por stdin): entre otros campos, trae
`session_id`, `transcript_path` (ruta a un JSONL con la transcripcion
completa de la sesion) y `stop_hook_active` (booleano; true si Claude Code
ya esta en un ciclo de continuacion disparado por un Stop hook previo en
este mismo turno -- evita loops).

Formato real de `transcript_path`, verificado leyendo un transcript real de
esta misma sesion de trabajo (no solo asumido del ADR): cada linea es un
objeto JSON independiente (JSONL). Las lineas de tipo "assistant" traen
`message.content`, una lista de bloques; los bloques de herramienta tienen
`type == "tool_use"`, `name` (el nombre de la herramienta, p.ej. "Edit" o
"Write") e `input` (los argumentos, incluyendo `file_path` para Edit/Write).
Esto es una anidacion mas profunda que la descripcion informal del ADR
("entradas tool_use con tool_name e input.file_path"), pero la misma senal
en sustancia -- no fue necesario recurrir a la alternativa de respaldo
(`git diff --name-only`) anotada en ADR-005, seccion "Alternativas
consideradas". Lineas de otros tipos (system, user, queue-operation,
attachment, etc.) se ignoran.

Logica (ver ADR-005 seccion "Decision" > "2. Diseno del hook Stop"):

1. Si `stop_hook_active` es true, salir con codigo 0 sin imprimir nada.
2. Leer y parsear `transcript_path` linea por linea, buscando bloques
   tool_use de Edit/Write cuyo `input.file_path` matchee alguno de los
   patrones protegidos (specs/*.md, docs/adr/DRAFT-*.md,
   docs/business-rules.md).
3. Si no hay ninguna coincidencia: salir con codigo 0, en silencio.
4. Si hay al menos una coincidencia: salir con codigo 2 e imprimir en
   stderr el recordatorio de AGENTS.md seccion 7.
5. Cualquier error de parseo (JSON invalido, transcript_path inexistente o
   ilegible) se trata igual que en protect_files.py: no bloquear por un
   problema del propio hook -- salir con codigo 0.
"""
import json
import re
import sys

FRICTION_SIGNAL_PATTERNS = [
    r"(^|/)specs/.*\.md$",
    r"(^|/)docs/adr/DRAFT-.*\.md$",
    r"(^|/)docs/business-rules\.md$",
]

REMINDER = (
    "[PKF] Esta sesion edito specs/, un DRAFT de ADR o business-rules.md. "
    "Antes de cerrar: ¿hay alguna friccion real de esta sesion que valga la "
    "pena proponer a docs/friction-log.md? Si si, anunciala explicitamente "
    "(que encontraste + tu intencion) antes de documentarla -- nunca la "
    "escribas en silencio (AGENTS.md seccion 7). Si no hay ninguna, dilo "
    "explicitamente y continua."
)


def _session_touched_protected_files(transcript_path: str) -> bool:
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                if block.get("name") not in ("Edit", "Write"):
                    continue
                file_path = block.get("input", {}).get("file_path", "") or ""
                for pattern in FRICTION_SIGNAL_PATTERNS:
                    if re.search(pattern, file_path):
                        return True
    return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("stop_hook_active"):
        sys.exit(0)

    transcript_path = data.get("transcript_path", "") or ""

    try:
        touched = _session_touched_protected_files(transcript_path)
    except (OSError, ValueError):
        # transcript_path inexistente/ilegible u otro problema de parseo:
        # no bloquear por un fallo del propio hook.
        sys.exit(0)

    if not touched:
        sys.exit(0)

    print(REMINDER, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
