"""Tests de `tools/add_business_rule.py` (ADR-006, seccion 2).

Se invoca como subproceso (igual que lo hace protect_bash_writes.py al
reconocerlo como excepcion sancionada) contra un `docs/business-rules.md`
de prueba autocontenido (fixture propia, no una copia del archivo real del
repo) -- para que estos tests no dependan de cuantas RN existan en el
proyecto que los ejecuta, y sigan siendo validos en un repo que use este
kit como plantilla, con business-rules.md vacio.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "tools" / "add_business_rule.py"

SAMPLE_BUSINESS_RULES = """\
# Reglas de negocio

> Registro único de reglas de negocio del proyecto. Ver formato en `CONVENTIONS.md`.
> Este archivo solo se modifica con instrucción explícita del dueño del proyecto (P2 de AGENTS.md).

**Próximo número disponible:** 003

---

### RN-001 — Regla de ejemplo uno

**Estado:** vigente
**Regla:** Enunciado de prueba verificable para RN-001.
**Origen:** Fixture de tests (tests/test_add_business_rule.py).
**Historial:**
- 2026-01-01 — creada.

---

### RN-002 — Regla de ejemplo dos

**Estado:** vigente
**Regla:** Enunciado de prueba verificable para RN-002.
**Origen:** Fixture de tests (tests/test_add_business_rule.py).
**Historial:**
- 2026-01-01 — creada.

---

<!-- PLANTILLA de regla — copiar y completar:

### RN-XXX — Título corto de la regla

**Estado:** vigente
**Regla:** enunciado preciso, verificable, sin ambigüedad.
**Origen:** contrato / cliente / normativa / decisión interna (referencia).
**Historial:**
- AAAA-MM-DD — creada.

-->
"""

# Numero "proximo numero disponible" segun la fixture de arriba (2 RN ya
# definidas). Construido en runtime para que tools/check_refs.py no lo
# interprete como una referencia real a una RN inexistente.
NEW_RN_NUMBER = "003"
NEW_RN_ID = "RN-" + NEW_RN_NUMBER


@pytest.fixture
def sandbox(tmp_path):
    """Escribe la fixture autocontenida de business-rules.md en un
    directorio temporal y hace que el script opere sobre esa copia."""
    sandbox_docs = tmp_path / "docs"
    sandbox_docs.mkdir()
    sandbox_rules = sandbox_docs / "business-rules.md"
    sandbox_rules.write_text(SAMPLE_BUSINESS_RULES, encoding="utf-8")
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
    assert "**Próximo número disponible:** 004" in after
    # No se toca el contenido previo (P5 -- nunca se borra historia).
    assert "### RN-001" in after
    assert "### RN-002" in after


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
            "--numero", "001",
            "--reemplazada-por", "RN-002",
            "--fecha", "2026-07-08",
        ],
        sandbox,
    )

    assert result.returncode == 0, result.stderr
    after = sandbox.read_text(encoding="utf-8")

    assert "**Estado:** obsoleta (reemplazada por RN-002, 2026-07-08)" in after
    assert "- 2026-07-08 — marcada obsoleta, reemplazada por RN-002." in after
    # El enunciado original de la regla no se toca.
    assert "Enunciado de prueba verificable para RN-001." in after
    # RN-002 sigue vigente, sin tocar.
    rn002_block = after.split("### RN-002")[1]
    assert "**Estado:** vigente" in rn002_block


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
        ["deprecate", "--numero", "001", "--reemplazada-por", "RN-002", "--fecha", "2026-07-09"],
        sandbox,
    )
    assert second.returncode != 0

    after_second = sandbox.read_text(encoding="utf-8")
    assert after_second == before_second
