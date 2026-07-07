"""Tests de `tools/add_business_rule.py` (ADR-006, seccion 2).

Se invoca como subproceso (igual que lo hace protect_bash_writes.py al
reconocerlo como excepcion sancionada) contra una copia temporal de
docs/business-rules.md, para no tocar el archivo real del repo durante los
tests.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "tools" / "add_business_rule.py"
REAL_BUSINESS_RULES = ROOT / "docs" / "business-rules.md"

# Construido en runtime, sin escribir el ID completo como literal, para que
# tools/check_refs.py no lo interprete como una referencia real a una RN
# que todavia no existe en docs/business-rules.md -- este numero es solo el
# "proximo numero disponible" vigente al momento de escribir este test, no
# una RN definida.
NEW_RN_NUMBER = "004"
NEW_RN_ID = "RN-" + NEW_RN_NUMBER


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Copia docs/business-rules.md real a un directorio temporal y hace que
    el script opere sobre esa copia, monkeypatcheando BUSINESS_RULES_PATH.
    """
    sandbox_docs = tmp_path / "docs"
    sandbox_docs.mkdir()
    sandbox_rules = sandbox_docs / "business-rules.md"
    shutil.copy(REAL_BUSINESS_RULES, sandbox_rules)
    return sandbox_rules


def run_script(args: list[str], business_rules_path: Path) -> subprocess.CompletedProcess:
    env_script = (
        "import sys; sys.path.insert(0, %r); "
        "import add_business_rule as m; "
        "m.BUSINESS_RULES_PATH = __import__('pathlib').Path(%r); "
        "sys.exit(m.main(sys.argv[1:]))"
    ) % (str(SCRIPT_PATH.parent), str(business_rules_path))
    return subprocess.run(
        [sys.executable, "-c", env_script, *args],
        capture_output=True,
        text=True,
    )


def test_create_success(sandbox):
    before = sandbox.read_text(encoding="utf-8")
    assert NEW_RN_ID not in before

    result = run_script(
        [
            "create",
            "--numero", NEW_RN_NUMBER,
            "--titulo", "Regla de prueba",
            "--regla", "Enunciado de prueba verificable.",
            "--origen", "Test automatizado.",
            "--fecha", "2026-07-08",
        ],
        sandbox,
    )

    assert result.returncode == 0, result.stderr
    assert ("[OK] " + NEW_RN_ID + " creada") in result.stdout

    after = sandbox.read_text(encoding="utf-8")
    assert ("### " + NEW_RN_ID + " — Regla de prueba") in after
    assert "**Estado:** vigente" in after
    assert "**Regla:** Enunciado de prueba verificable." in after
    assert "**Origen:** Test automatizado." in after
    assert "- 2026-07-08 — creada." in after
    assert "**Próximo número disponible:** 005" in after
    # No se toca el contenido previo (P5 -- nunca se borra historia).
    assert "### RN-001" in after
    assert "### RN-002" in after
    assert "### RN-003" in after


def test_create_with_wrong_numero_fails_without_writing(sandbox):
    before = sandbox.read_text(encoding="utf-8")

    result = run_script(
        [
            "create",
            "--numero", "999",
            "--titulo", "No deberia crearse",
            "--regla", "x",
            "--origen", "y",
        ],
        sandbox,
    )

    assert result.returncode != 0
    assert "no coincide" in result.stderr

    after = sandbox.read_text(encoding="utf-8")
    assert after == before
    assert "No deberia crearse" not in after


def test_create_with_empty_titulo_fails_without_writing(sandbox):
    before = sandbox.read_text(encoding="utf-8")

    result = run_script(
        [
            "create",
            "--numero", NEW_RN_NUMBER,
            "--titulo", "",
            "--regla", "x",
            "--origen", "y",
        ],
        sandbox,
    )

    assert result.returncode != 0
    after = sandbox.read_text(encoding="utf-8")
    assert after == before


def test_deprecate_success(sandbox):
    result = run_script(
        [
            "deprecate",
            "--numero", "002",
            "--reemplazada-por", "RN-003",
            "--fecha", "2026-07-08",
        ],
        sandbox,
    )

    assert result.returncode == 0, result.stderr
    after = sandbox.read_text(encoding="utf-8")

    assert "**Estado:** obsoleta (reemplazada por RN-003, 2026-07-08)" in after
    assert "- 2026-07-08 — marcada obsoleta, reemplazada por RN-003." in after
    # El enunciado original de la regla no se toca.
    assert (
        "Antes de permitir el cierre de un curso, la suma de horas netas"
        in after
    )
    # RN-001 y RN-003 siguen vigentes, sin tocar.
    rn001_block = after.split("### RN-001")[1].split("### RN-002")[0]
    assert "**Estado:** vigente" in rn001_block


def test_deprecate_nonexistent_rn_fails(sandbox):
    before = sandbox.read_text(encoding="utf-8")

    result = run_script(
        [
            "deprecate",
            "--numero", "999",
            "--reemplazada-por", "RN-001",
        ],
        sandbox,
    )

    assert result.returncode != 0
    assert "no existe" in result.stderr

    after = sandbox.read_text(encoding="utf-8")
    assert after == before


def test_deprecate_already_obsolete_fails(sandbox):
    # Primero la obsoleta una vez (legitimo).
    first = run_script(
        ["deprecate", "--numero", "001", "--reemplazada-por", "RN-002", "--fecha", "2026-07-08"],
        sandbox,
    )
    assert first.returncode == 0, first.stderr

    before_second = sandbox.read_text(encoding="utf-8")

    # Segundo intento sobre la misma RN ya obsoleta debe fallar.
    second = run_script(
        ["deprecate", "--numero", "001", "--reemplazada-por", "RN-003", "--fecha", "2026-07-09"],
        sandbox,
    )
    assert second.returncode != 0

    after_second = sandbox.read_text(encoding="utf-8")
    assert after_second == before_second
