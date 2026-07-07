#!/usr/bin/env bash
# SessionStart hook — se dispara al iniciar, resumir o limpiar una sesion.
# Su stdout se agrega como contexto que Claude puede ver de entrada, asi que
# ya no depende de que el agente decida leer AGENTS.md por su cuenta.

AGENTS_FILE="$CLAUDE_PROJECT_DIR/AGENTS.md"

if [ -f "$AGENTS_FILE" ]; then
  echo "=== CONTRATO DE COLABORACION IA (AGENTS.md) — cargado automaticamente por PKF ==="
  cat "$AGENTS_FILE"
  echo "=== FIN AGENTS.md ==="
else
  echo "[PKF] Aviso: no se encontro AGENTS.md en $AGENTS_FILE" >&2
fi

exit 0
