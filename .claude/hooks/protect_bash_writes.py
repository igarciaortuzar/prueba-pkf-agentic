#!/usr/bin/env python3
"""PreToolUse hook: bloquea escrituras directas via Bash a archivos
protegidos de PKF (AGENTS.md, docs/business-rules.md, ADRs ya aceptados).

Ver ADR-006 (docs/adr/ADR-006-hook-proteccion-bash.md) para el diseno
completo y su razonamiento. Este hook complementa a protect_files.py
(que cubre Edit/Write) cerrando el hueco que motivo la friccion registrada
en docs/friction-log.md (entrada 2026-07-07, "La proteccion de archivos
(hook PreToolUse) no cubre Bash"): un heredoc de Bash pudo escribir
contenido nuevo en docs/business-rules.md sin pasar por ningun guardrail.

IMPORTANTE - esto es una heuristica de texto sobre el comando de shell, no
una senal perfecta (Bash no entrega un file_path discreto como Edit/Write).
Ver ADR-006 seccion "Consecuencias" para los limites honestos aceptados:
falsos negativos por ofuscacion de ruta o herramientas no listadas, falsos
positivos acotados (lectura de un archivo protegido junto a escritura de
otro archivo en el mismo comando).

Logica (en orden, ver ADR-006 seccion "Decision" > "1. Logica de deteccion"):

1. Short-circuit barato: si el comando no menciona ningun patron de
   PROTECTED_PATTERNS (busqueda de texto, sin anclas de path completo),
   se permite de inmediato sin ningun analisis adicional.
2. Excepcion 1 - promocion de ADR: mv/git mv de dos argumentos exactos
   DRAFT-<slug>.md -> ADR-0XX-<slug>.md con el mismo slug, sin encadenar
   con otros comandos. Se permite.
3. Excepcion 2 - script sancionado: invocacion (sin encadenar) de
   `python tools/add_business_rule.py ...`. Se permite; la validacion de
   fondo la hace el propio script.
4. Caso general: si hay mencion de archivo protegido y no calzo ninguna
   excepcion, se bloquea (exit 2) si ademas aparece un token que "parece"
   una escritura (>, >>, sed -i, tee, cp , etc., o un mv/git mv que no
   calzo exactamente la excepcion 1). `>` y `tee` se verifican por su
   DESTINO real (no por mencion en cualquier parte del comando): solo
   bloquean si el archivo inmediatamente despues de `>`/`tee` es uno
   protegido. Esto es lo que permite que un mensaje de `git commit` que
   menciona "AGENTS.md" en prosa, o contiene un ">" dentro de un email
   "Co-Authored-By: ... <email>", no se bloquee -- sin necesitar una
   excepcion especial para `git commit` (una version anterior de este hook
   sí tenía una excepcion 3 categorica para `git commit`; se revirtio por
   ser un cambio al limite de seguridad que ADR-006 no aprobo -- ver
   docs/friction-log.md). Si solo hay mencion sin token de escritura
   (lectura), se permite.
"""
import json
import re
import sys

from protected_patterns import PROTECTED_PATTERNS

# Patrones de "mencion" derivados de PROTECTED_PATTERNS, sin las anclas de
# path completo ((^|/) ... $) que protect_files.py usa para matchear un
# file_path discreto. Un comando de Bash no es un path limpio -- el nombre
# de archivo protegido puede aparecer en medio del string (ej. seguido de
# " | tee /tmp/copia.md"), asi que se busca el nombre de archivo literal en
# cualquier posicion. Se derivan de la misma lista (no se duplican a mano)
# para que un archivo protegido nuevo agregado en protected_patterns.py
# quede cubierto aqui automaticamente.


def _strip_anchors(pattern: str) -> str:
    p = pattern
    if p.startswith("(^|/)"):
        p = p[len("(^|/)"):]
    if p.endswith("$"):
        p = p[:-1]
    return p


MENTION_PATTERNS = [_strip_anchors(p) for p in PROTECTED_PATTERNS]

# Excepcion 1: mv/git mv de promocion de ADR, dos argumentos exactos,
# mismo slug en origen (DRAFT-<slug>.md) y destino (ADR-0XX-<slug>.md).
ADR_PROMOTION_RE = re.compile(
    r"^(git\s+mv|mv)\s+(\S*/)?DRAFT-([a-z0-9-]+)\.md\s+(\S*/)?ADR-\d{3}-\3\.md\s*$"
)

# Excepcion 2: invocacion del script sancionado para crear/obsoletar RN.
ADD_BUSINESS_RULE_RE = re.compile(r"^(python3?|py)\s+tools/add_business_rule\.py\b.*$")

# Separadores de shell que descalifican una linea de comando para cualquiera
# de las excepciones de un solo comando (deben ser un unico comando, no
# encadenado).
_CHAINING_TOKENS = (";", "&&", "||", "|", "`", "$(")

# Tokens de escritura que son suficientemente distintivos como substring
# libre (baja probabilidad de aparecer por accidente en prosa normal o en
# subcomandos de git comunes).
WRITE_TOKENS = (
    "sed -i",
    "cp ",
    "install ",
    "rsync",
    "perl -i",
    "truncate",
)

# "dd" necesita contexto de palabra completa (precedido de espacio o inicio
# de linea): como substring libre matcheaba dentro de "git add " (el
# comando de git mas usado en este flujo de trabajo). ">" y "tee" ya no se
# verifican por substring/mencion: se verifica su destino real (funciones
# _redirect_targets/_tee_targets mas abajo), porque incluso exigiendo
# contexto de palabra, "seccion 'X' > 'Y'" (notacion de prosa que aparece
# constantemente en specs/ADRs de este proyecto) tiene la misma forma de
# superficie que un redirect real y seguia dando falsos positivos.
DD_RE = re.compile(r"(?:^|\s)dd(?:\s|$)")


def _is_single_command(command: str) -> bool:
    """True si el comando no encadena con otro comando via separadores de
    shell (;, &&, ||, |, backticks, $(...)) ni tiene saltos de linea fuera
    de un trailing newline."""
    body = command[:-1] if command.endswith("\n") else command
    if "\n" in body:
        return False
    return not any(tok in body for tok in _CHAINING_TOKENS)


def _mentions_protected_file(command: str) -> bool:
    return any(re.search(pattern, command) for pattern in MENTION_PATTERNS)


def _matches_adr_promotion_exception(command: str) -> bool:
    if not _is_single_command(command):
        return False
    return bool(ADR_PROMOTION_RE.match(command.strip()))


def _matches_add_business_rule_exception(command: str) -> bool:
    if not _is_single_command(command):
        return False
    return bool(ADD_BUSINESS_RULE_RE.match(command.strip()))


def _redirect_targets(command: str) -> list:
    """Tokens que serian el archivo destino de un '>'/'>>' precedido de
    espacio o inicio de linea. P.ej. en 'echo x >> foo.md' devuelve
    ['foo.md']."""
    return [m.group(1) for m in re.finditer(r"(?:^|\s)>{1,2}\s*(\S+)", command)]


def _tee_targets(command: str) -> list:
    """Tokens que serian el/los archivo(s) destino de 'tee' (su primer
    argumento posicional tras flags como -a). Solo el primer token: `tee`
    real casi siempre toma un unico archivo destino inmediatamente despues;
    capturar TODOS los tokens restantes de la linea (version anterior de
    esta funcion) hacia que prosa como 'documenta tee en AGENTS.md' contara
    "AGENTS.md" como si fuera un destino de tee, aunque estuviera a varias
    palabras de distancia -- ver docs/friction-log.md."""
    targets = []
    for m in re.finditer(r"\btee\b(?:\s+-\S+)*\s+(\S+)", command):
        targets.append(m.group(1))
    return targets


def _mentions_protected_file_in_targets(targets: list) -> bool:
    return any(
        re.search(pattern, target) for target in targets for pattern in MENTION_PATTERNS
    )


def _looks_like_write(command: str) -> bool:
    # ">"/"tee" se verifican por destino real, no por mencion en cualquier
    # parte del comando: "seccion 'X' > 'Y'" (notacion de prosa, no un
    # redirect real) tiene la misma forma de superficie que un redirect,
    # pero su "destino" no es un archivo protegido. Ver docs/friction-log.md,
    # entrada "El hook de proteccion de Bash bloqueo un commit legitimo".
    if _mentions_protected_file_in_targets(_redirect_targets(command)):
        return True
    if _mentions_protected_file_in_targets(_tee_targets(command)):
        return True
    if any(tok in command for tok in WRITE_TOKENS):
        return True
    if DD_RE.search(command):
        return True
    # mv/git mv que no calzo exactamente con la excepcion 1 tambien cuenta
    # como escritura (renombrar/mover un archivo protegido).
    if re.search(r"(^|[;&|`]|\s)(git\s+mv|mv)(\s|$)", command):
        return True
    return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "") or ""

    # 1. Short-circuit: si no menciona ningun archivo protegido, se permite.
    if not _mentions_protected_file(command):
        sys.exit(0)

    # 2. Excepcion 1: promocion de ADR (mv/git mv exacto).
    if _matches_adr_promotion_exception(command):
        sys.exit(0)

    # 3. Excepcion 2: script sancionado para RN.
    if _matches_add_business_rule_exception(command):
        sys.exit(0)

    # 4. Caso general: bloquea solo si ademas parece una escritura.
    if _looks_like_write(command):
        print(
            "[PKF] BLOQUEADO: este comando de Bash parece escribir "
            "directamente sobre un archivo protegido (AGENTS.md, "
            "docs/business-rules.md o un ADR ya aceptado). Este hook "
            "(ADR-006, docs/adr/ADR-006-hook-proteccion-bash.md) bloquea "
            "escrituras directas via Bash a esas rutas, igual que "
            "protect_files.py ya bloquea Edit/Write sobre ellas. Si el "
            "cambio es legitimo:\n"
            "  - Para crear/obsoletar una regla de negocio: usa "
            "`python tools/add_business_rule.py create|deprecate ...` "
            "(unico camino sancionado).\n"
            "  - Para promover un ADR: `git mv docs/adr/DRAFT-<slug>.md "
            "docs/adr/ADR-0XX-<slug>.md` como comando unico, sin encadenar "
            "con nada mas.\n"
            "  - Para AGENTS.md u otro caso no cubierto por lo anterior: "
            "edita el archivo tu mismo fuera de este flujo (Edit/Write, "
            "revisando el diff linea por linea) en vez de Bash.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Mencion sin token de escritura -- probablemente una lectura
    # (cat, grep, git diff, etc.). Se permite.
    sys.exit(0)


if __name__ == "__main__":
    main()
