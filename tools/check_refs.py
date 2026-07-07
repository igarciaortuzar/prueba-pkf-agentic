#!/usr/bin/env python3
"""
check_refs.py — Linter mínimo de trazabilidad para PKF v0.1.

Verifica que:
  1. Todo RN-xxx referenciado en el repo esté definido en docs/business-rules.md.
  2. Todo ADR-xxx referenciado exista como archivo en docs/adr/.
  3. No haya IDs de RN duplicados.
  4. (Aviso) RNs definidas que nadie referencia (huérfanas).

Uso:  python tools/check_refs.py   (desde la raíz del repo)
Sale con código 1 si hay errores; los avisos no bloquean.
"""

import re
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

def find_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
            return parent
    return current


ROOT = find_root()
RN_DEF = re.compile(r"^###\s+(RN-\d{3})\b", re.MULTILINE)
RN_REF = re.compile(r"\b(RN-\d{3})\b")
ADR_REF = re.compile(r"\b(ADR-\d{3})\b")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "examples", "testing", ".claude", ".vscode"}
TEXT_EXT = {".md", ".py", ".yaml", ".yml", ".json", ".txt", ".sql", ".js", ".ts"}


def text_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in TEXT_EXT and not (set(p.parts) & SKIP_DIRS):
            yield p


def main() -> int:
    errors, warnings = [], []

    # --- RN definidas ---
    br = ROOT / "docs" / "business-rules.md"
    defined_rn = []
    if br.exists():
        defined_rn = RN_DEF.findall(br.read_text(encoding="utf-8"))
    dupes = {x for x in defined_rn if defined_rn.count(x) > 1}
    for d in sorted(dupes):
        errors.append(f"RN duplicada en business-rules.md: {d}")
    defined_rn_set = set(defined_rn)

    # --- ADR existentes ---
    adr_dir = ROOT / "docs" / "adr"
    existing_adr = set()
    if adr_dir.exists():
        for f in adr_dir.glob("ADR-*.md"):
            m = re.match(r"(ADR-\d{3})", f.name)
            if m:
                existing_adr.add(m.group(1))

    # --- Referencias en todo el repo ---
    referenced_rn, referenced_adr = {}, {}
    for f in text_files():
        rel = f.relative_to(ROOT)
        content = f.read_text(encoding="utf-8", errors="ignore")
        if "TEMPLATE" in f.name.upper():
            continue  # las plantillas usan XXX y ejemplos
        for rn in RN_REF.findall(content):
            referenced_rn.setdefault(rn, []).append(str(rel))
        for adr in ADR_REF.findall(content):
            referenced_adr.setdefault(adr, []).append(str(rel))

    # 1. RN referenciadas pero no definidas
    for rn, files in sorted(referenced_rn.items()):
        if rn in defined_rn_set:
            continue
        non_mention_only_in_rules_file = [x for x in files if x != "docs/business-rules.md"]
        # si la única mención está en business-rules.md pero no está definida
        # ahí como "### RN-xxx", igual es un error (RN mal formada)
        reportable_files = non_mention_only_in_rules_file or files
        errors.append(f"{rn} referenciada pero no definida — en: {', '.join(sorted(set(reportable_files)))}")

    # 2. ADR referenciados pero inexistentes
    for adr, files in sorted(referenced_adr.items()):
        files_out = sorted({x for x in files if not x.startswith("docs/adr/" + adr)})
        if adr not in existing_adr:
            errors.append(f"{adr} referenciado pero no existe archivo en docs/adr/ — en: {', '.join(files_out)}")

    # 3. RN huérfanas (aviso)
    for rn in sorted(defined_rn_set):
        uses = {x for x in referenced_rn.get(rn, []) if x != "docs/business-rules.md"}
        if not uses:
            warnings.append(f"{rn} definida pero nadie la referencia (¿huérfana?)")

    for w in warnings:
        print(f"AVISO  {w}")
    for e in errors:
        print(f"ERROR  {e}")

    if errors:
        print(f"\n{len(errors)} error(es), {len(warnings)} aviso(s).")
        return 1
    print(f"OK — referencias consistentes ({len(defined_rn_set)} RN, {len(existing_adr)} ADR). {len(warnings)} aviso(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
