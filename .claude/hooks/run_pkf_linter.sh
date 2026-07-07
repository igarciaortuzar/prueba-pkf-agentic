#!/usr/bin/env bash
# PostToolUse hook — corre DESPUES de que Edit/Write ya se ejecuto.
# El linter de referencia de PKF (tools/check_refs.py) valida todo el repo
# (no toma un archivo puntual como argumento: revisa trazabilidad de RN-xxx
# y ADR-xxx en conjunto). Si encuentra problemas, salimos con codigo 2:
# Claude ve el error y tiene que corregir antes de seguir (no puede ignorarlo
# silenciosamente, a diferencia de una regla que solo vive en AGENTS.md).

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('tool_input', {}).get('file_path', ''))
")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

LINT_CMD="python3 \"$CLAUDE_PROJECT_DIR/tools/check_refs.py\""

if ! eval "$LINT_CMD" 1>&2; then
  echo "[PKF] El linter de referencia (tools/check_refs.py) encontro problemas tras editar '$FILE_PATH'. Corrige antes de continuar." >&2
  exit 2
fi

exit 0
