#!/usr/bin/env python3
"""
add_business_rule.py — único camino sancionado para crear/obsoletar reglas
de negocio (RN-xxx) en docs/business-rules.md desde Bash, dentro de una
sesión de Claude Code, invocado con instrucción explícita del dueño del
proyecto (P2 de AGENTS.md).

Ver docs/orquestacion-claude-code.md, sección "Protección de Bash contra
escrituras directas a archivos protegidos". `protect_bash_writes.py`
reconoce la invocación de este script como una excepción explícita al
bloqueo general de escrituras vía Bash sobre docs/business-rules.md — la
validación de fondo (formato, numeración, atomicidad) la hace este script,
no el hook.

No verifica quién invoca el script ni si hubo, en efecto, instrucción
explícita del dueño — eso sigue siendo responsabilidad del agente/sesión de
Claude Code (limitación reconocida y aceptada).

Uso:

    python tools/add_business_rule.py create \\
      --numero 004 \\
      --titulo "Título corto de la regla" \\
      --regla "Enunciado preciso, verificable, sin ambigüedad." \\
      --origen "Contrato / cliente / normativa / decisión interna (referencia)." \\
      [--fecha 2026-07-08]

    python tools/add_business_rule.py deprecate \\
      --numero 002 \\
      --reemplazada-por RN-0NN \\
      [--fecha 2026-07-08]

Sale con código distinto de cero y no toca el archivo si cualquier
validación falla (mensaje claro en stderr).
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUSINESS_RULES_PATH = ROOT / "docs" / "business-rules.md"

NEXT_NUMBER_RE = re.compile(r"\*\*Próximo número disponible:\*\*\s*(\d{3})")
NUMERO_RE = re.compile(r"^\d{3}$")
RN_ID_RE = re.compile(r"^RN-\d{3}$")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLANTILLA_MARKER = "<!-- PLANTILLA"
FORBIDDEN_TEXT_SEQUENCES = ("### RN-", "**Estado:**")


def _display_path() -> str:
    """Ruta legible de BUSINESS_RULES_PATH para mensajes de stdout. Usa una
    ruta relativa a ROOT cuando es posible (uso normal); cae a la ruta tal
    cual si BUSINESS_RULES_PATH fue reasignado a otra ubicacion (por
    ejemplo, en tests que apuntan a un archivo temporal fuera del repo)."""
    try:
        return str(BUSINESS_RULES_PATH.relative_to(ROOT))
    except ValueError:
        return str(BUSINESS_RULES_PATH)


class ValidationError(Exception):
    """Cualquier fallo de validación antes de escribir el archivo."""


def _today() -> str:
    return datetime.date.today().isoformat()


def _validate_fecha(fecha: str | None) -> str:
    if fecha is None:
        return _today()
    if not FECHA_RE.match(fecha):
        raise ValidationError(f"--fecha '{fecha}' no tiene formato AAAA-MM-DD.")
    try:
        datetime.date.fromisoformat(fecha)
    except ValueError as exc:
        raise ValidationError(f"--fecha '{fecha}' no es una fecha válida: {exc}") from exc
    return fecha


def _validate_text_field(name: str, value: str) -> str:
    if not value or not value.strip():
        raise ValidationError(f"--{name} no puede estar vacío.")
    if "\n" in value:
        raise ValidationError(f"--{name} no puede contener saltos de línea.")
    for seq in FORBIDDEN_TEXT_SEQUENCES:
        if seq in value:
            raise ValidationError(
                f"--{name} no puede contener la secuencia '{seq}' "
                f"(evita inyectar bloques Markdown o alterar el Estado de otra RN)."
            )
    return value


def _read_business_rules() -> str:
    if not BUSINESS_RULES_PATH.exists():
        raise ValidationError(f"No existe {BUSINESS_RULES_PATH}.")
    return BUSINESS_RULES_PATH.read_text(encoding="utf-8")


def _current_next_number(content: str) -> str:
    m = NEXT_NUMBER_RE.search(content)
    if not m:
        raise ValidationError(
            "No se encontró la línea '**Próximo número disponible:** NNN' "
            f"en {BUSINESS_RULES_PATH} en el formato esperado."
        )
    return m.group(1)


def _atomic_write(content: str) -> None:
    """Escribe docs/business-rules.md de forma atomica: archivo temporal en
    el mismo directorio + os.replace, para no dejar el archivo a medio
    escribir si algo falla a mitad de la escritura (ver docs/orquestacion-claude-code.md).
    """
    tmp_path = str(BUSINESS_RULES_PATH) + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, BUSINESS_RULES_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def cmd_create(args: argparse.Namespace) -> int:
    if not NUMERO_RE.match(args.numero or ""):
        raise ValidationError(f"--numero '{args.numero}' debe tener formato NNN (3 dígitos).")

    titulo = _validate_text_field("titulo", args.titulo)
    regla = _validate_text_field("regla", args.regla)
    origen = _validate_text_field("origen", args.origen)
    fecha = _validate_fecha(args.fecha)

    content = _read_business_rules()
    next_number = _current_next_number(content)

    if args.numero != next_number:
        raise ValidationError(
            f"--numero '{args.numero}' no coincide con el 'Próximo número "
            f"disponible' vigente ('{next_number}'). No se escribió nada. "
            f"Vuelve a invocar el comando con --numero {next_number}."
        )

    if PLANTILLA_MARKER not in content:
        raise ValidationError(
            f"No se encontró el marcador '{PLANTILLA_MARKER}' en "
            f"{BUSINESS_RULES_PATH}; no se puede ubicar dónde insertar la RN nueva."
        )

    rn_id = f"RN-{args.numero}"
    block = (
        f"### {rn_id} — {titulo}\n"
        f"\n"
        f"**Estado:** vigente\n"
        f"**Regla:** {regla}\n"
        f"**Origen:** {origen}\n"
        f"**Historial:**\n"
        f"- {fecha} — creada.\n"
        f"\n"
        f"---\n"
        f"\n"
    )

    new_content = content.replace(PLANTILLA_MARKER, block + PLANTILLA_MARKER, 1)

    new_number_int = int(args.numero) + 1
    new_next_number = f"{new_number_int:03d}"
    new_content = NEXT_NUMBER_RE.sub(
        f"**Próximo número disponible:** {new_next_number}", new_content, count=1
    )

    _atomic_write(new_content)

    print(f"[OK] {rn_id} creada en {_display_path()}.")
    print(f"  Título: {titulo}")
    print(f"  Estado: vigente")
    print(f"  Regla: {regla}")
    print(f"  Origen: {origen}")
    print(f"  Historial: - {fecha} — creada.")
    print(f"  Próximo número disponible actualizado: {next_number} -> {new_next_number}")
    return 0


def cmd_deprecate(args: argparse.Namespace) -> int:
    if not NUMERO_RE.match(args.numero or ""):
        raise ValidationError(f"--numero '{args.numero}' debe tener formato NNN (3 dígitos).")

    if not args.reemplazada_por:
        raise ValidationError(
            "--reemplazada-por es obligatorio: el formato de escritura de "
            "'obsoleta' siempre registra qué RN la reemplaza (ver docs/orquestacion-claude-code.md)."
        )
    if not RN_ID_RE.match(args.reemplazada_por):
        raise ValidationError(
            f"--reemplazada-por '{args.reemplazada_por}' debe tener formato RN-NNN."
        )

    fecha = _validate_fecha(args.fecha)

    content = _read_business_rules()
    rn_id = f"RN-{args.numero}"

    block_re = re.compile(
        rf"(?ms)^### {re.escape(rn_id)} — .*?(?=^### RN-\d{{3}} — |^{re.escape(PLANTILLA_MARKER)}|\Z)"
    )
    match = block_re.search(content)
    if not match:
        raise ValidationError(f"{rn_id} no existe en {BUSINESS_RULES_PATH}.")

    block = match.group(0)

    if "**Estado:** vigente" not in block:
        raise ValidationError(
            f"{rn_id} no tiene Estado: vigente (ya está obsoleta o el formato "
            f"no es el esperado) — no se puede obsoletar dos veces."
        )

    new_estado_line = (
        f"**Estado:** obsoleta (reemplazada por {args.reemplazada_por}, {fecha})"
    )
    new_block = block.replace("**Estado:** vigente", new_estado_line, 1)

    historial_re = re.compile(r"(\*\*Historial:\*\*\n(?:- .*\n)+)")
    hm = historial_re.search(new_block)
    if not hm:
        raise ValidationError(
            f"No se encontró la sección '**Historial:**' de {rn_id} en el "
            f"formato esperado; no se modificó el archivo."
        )
    new_historial_line = (
        f"- {fecha} — marcada obsoleta, reemplazada por {args.reemplazada_por}.\n"
    )
    new_historial_block = hm.group(1) + new_historial_line
    new_block = new_block[: hm.start()] + new_historial_block + new_block[hm.end():]

    new_content = content[: match.start()] + new_block + content[match.end():]

    _atomic_write(new_content)

    print(f"[OK] {rn_id} marcada obsoleta en {_display_path()}.")
    print(f"  {new_estado_line}")
    print(f"  Historial agregado: {new_historial_line.strip()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Único camino sancionado para crear/obsoletar RN vía Bash."
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    create_p = sub.add_parser("create", help="Crea una RN nueva.")
    create_p.add_argument("--numero", required=True, help="Formato NNN (3 dígitos).")
    create_p.add_argument("--titulo", required=True)
    create_p.add_argument("--regla", required=True)
    create_p.add_argument("--origen", required=True)
    create_p.add_argument("--fecha", required=False, default=None, help="AAAA-MM-DD (default: hoy).")
    create_p.set_defaults(func=cmd_create)

    deprecate_p = sub.add_parser("deprecate", help="Marca una RN existente como obsoleta.")
    deprecate_p.add_argument("--numero", required=True, help="Formato NNN (3 dígitos).")
    deprecate_p.add_argument("--reemplazada-por", dest="reemplazada_por", required=True, help="Formato RN-NNN.")
    deprecate_p.add_argument("--fecha", required=False, default=None, help="AAAA-MM-DD (default: hoy).")
    deprecate_p.set_defaults(func=cmd_deprecate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValidationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
