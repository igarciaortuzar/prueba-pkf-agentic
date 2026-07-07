"""Tests del hook `PreToolUse` sobre `Bash` (ADR-006).

Se invoca el hook como subproceso (igual que lo hace Claude Code:
JSON del evento por stdin, se evalua el codigo de salida) en vez de
importar sus funciones, para probar el mismo contrato que usa el runtime
real -- ver docs/adr/ADR-006-hook-proteccion-bash.md.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = ROOT / ".claude" / "hooks" / "protect_bash_writes.py"


def run_hook(command: str, tool_name: str = "Bash") -> subprocess.CompletedProcess:
    event = {"tool_name": tool_name, "tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )


def test_blocks_heredoc_to_business_rules():
    command = (
        "cat >> docs/business-rules.md << 'EOF'\n"
        "### RN-0XX — inyectada\n"
        "EOF\n"
    )
    result = run_hook(command)
    assert result.returncode == 2
    assert "BLOQUEADO" in result.stderr


def test_blocks_sed_i_to_agents_md():
    result = run_hook("sed -i 's/foo/bar/' AGENTS.md")
    assert result.returncode == 2
    assert "BLOQUEADO" in result.stderr


def test_allows_exact_adr_promotion_git_mv():
    result = run_hook(
        "git mv docs/adr/DRAFT-hook-proteccion-bash.md "
        "docs/adr/ADR-006-hook-proteccion-bash.md"
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_allows_exact_adr_promotion_mv_without_git():
    result = run_hook("mv docs/adr/DRAFT-mi-slug.md docs/adr/ADR-006-mi-slug.md")
    assert result.returncode == 0


def test_blocks_adr_promotion_with_mismatched_slug():
    result = run_hook("mv docs/adr/DRAFT-slug-a.md docs/adr/ADR-006-slug-b.md")
    assert result.returncode == 2


def test_allows_add_business_rule_script_invocation():
    result = run_hook(
        "python tools/add_business_rule.py create --numero 004 "
        "--titulo 'x' --regla 'y' --origen 'z'"
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_allows_normal_commands_that_dont_mention_protected_files():
    for command in [
        "pytest",
        "git status",
        "python tools/check_refs.py",
        "git log --oneline -5",
        "ls -la",
        "echo hello > /tmp/scratch.txt",
    ]:
        result = run_hook(command)
        assert result.returncode == 0, f"comando inesperadamente bloqueado: {command!r}"


def test_blocks_chained_adr_promotion_plus_write_to_business_rules():
    command = (
        "git mv docs/adr/DRAFT-x.md docs/adr/ADR-006-x.md && "
        "echo 'texto' >> docs/business-rules.md"
    )
    result = run_hook(command)
    assert result.returncode == 2
    assert "BLOQUEADO" in result.stderr


def test_allows_read_only_mention_of_protected_file():
    result = run_hook("cat docs/business-rules.md")
    assert result.returncode == 0

    result = run_hook("grep RN-001 docs/business-rules.md")
    assert result.returncode == 0

    result = run_hook("git diff AGENTS.md")
    assert result.returncode == 0


def test_ignores_non_bash_tool():
    result = run_hook("cualquier cosa", tool_name="Write")
    assert result.returncode == 0


def test_allows_git_commit_mentioning_protected_file_in_message():
    """Regresion: un commit real de esta sesion quedo bloqueado porque su
    mensaje mencionaba AGENTS.md y contenia '<noreply@anthropic.com>' -- el
    '>' del email se interpreto como token de escritura. NO se resuelve con
    una excepcion categorica para 'git commit' (eso se probo, y se revirtio:
    era un cambio al limite de seguridad que ADR-006 no aprobo, ver
    docs/friction-log.md) -- se resuelve porque '>'/'tee' ahora se verifican
    por su destino real, y '<...>' no tiene un destino real despues del '>'
    (no hay espacio antes)."""
    message = (
        "Actualiza AGENTS.md seccion 7.\n\n"
        "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
    )
    result = run_hook(f"git commit -m {message!r}")
    assert result.returncode == 0
    assert result.stderr == ""


def test_allows_git_commit_mentioning_tee_as_prose_word():
    """La verificacion por destino real de 'tee' evita el falso positivo de
    'committee'/prosa incluso dentro de un git commit, sin necesitar una
    excepcion especial para git commit."""
    message = "El comite (committee) reviso la seccion de AGENTS.md ayer"
    result = run_hook(f"git commit -m {message!r}")
    assert result.returncode == 0


def test_git_commit_mentioning_sed_i_as_prose_is_a_known_accepted_limitation():
    """LIMITACION CONOCIDA Y ACEPTADA, no un bug: a diferencia de '>'/'tee',
    'sed -i' (y cp /install /rsync/perl -i/truncate) siguen siendo
    mencion+substring, no verificacion por destino real -- ver ADR-006 y
    docs/friction-log.md ('riesgo vigilado'). Un commit cuyo mensaje
    describe 'sed -i' en prosa junto a un archivo protegido SI se bloquea
    hoy. Se probo agregar una excepcion categorica para git commit (que
    habria evitado esto), pero se revirtio por ser un cambio de arquitectura
    no aprobado via ADR (ver friction-log). Este test documenta el
    comportamiento actual a proposito, para que un cambio futuro que lo
    modifique lo haga con intencion, no por accidente."""
    message = "Documenta sed -i como ejemplo de token de escritura en AGENTS.md"
    result = run_hook(f"git commit -m {message!r}")
    assert result.returncode == 2


def test_git_commit_with_file_flag_is_unaffected():
    result = run_hook("git commit -F /tmp/mensaje-de-commit.txt")
    assert result.returncode == 0


def test_angle_bracket_email_does_not_trigger_redirect_false_positive():
    """Regresion: '<email@dominio.com>' no debe contar como redireccion de
    shell solo porque contiene un '>' -- se exige espacio/inicio de linea
    antes del '>' (forma tipica de 'cmd > archivo')."""
    result = run_hook("echo 'contacto: <alguien@dominio.com> ver AGENTS.md'")
    assert result.returncode == 0


def test_committee_word_does_not_trigger_tee_false_positive():
    """Regresion: 'committee' contiene 'tee' como substring; no debe
    bloquear un comando de solo lectura/prosa sobre AGENTS.md."""
    result = run_hook("echo 'el committee reviso AGENTS.md ayer'")
    assert result.returncode == 0


def test_git_add_mentioning_protected_file_does_not_trigger_dd_false_positive():
    """Regresion: 'git add AGENTS.md' quedo bloqueado porque 'add ' contiene
    'dd ' como substring -- el comando de git mas comun de este flujo de
    trabajo (preparar un commit) se rompia cada vez que la lista de
    archivos incluia un archivo protegido."""
    result = run_hook(
        "git add AGENTS.md docs/business-rules.md docs/adr/ADR-006-x.md"
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_real_dd_command_to_protected_file_still_blocked_after_fix():
    result = run_hook("dd if=/dev/zero of=AGENTS.md")
    assert result.returncode == 2


def test_prose_arrow_notation_does_not_trigger_redirect_false_positive():
    """Regresion (encontrada por pkf-auditor): 'seccion X > Y' es notacion
    de prosa usada constantemente en specs/ADRs de este proyecto para citar
    subsecciones -- tiene la misma forma de superficie que un redirect real
    (espacio + '>') pero su 'destino' no es un archivo. Ahora se verifica
    el destino real del '>', no solo su presencia."""
    result = run_hook(
        "echo revisando docs/adr/ADR-006-hook-proteccion-bash.md "
        "seccion 'Decision' > '2. Diseno de tools/add_business_rule.py'"
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_tee_target_extraction_ignores_flags():
    """'tee -a archivo.md' -- el destino es el argumento tras el flag, no
    el flag mismo."""
    result = run_hook("echo x | tee -a AGENTS.md")
    assert result.returncode == 2


def test_real_redirect_to_protected_file_still_blocked_after_fix():
    """Los fixes de falsos positivos no deben debilitar la deteccion real:
    un '>' precedido de espacio (forma normal de un redirect) sigue
    bloqueando."""
    result = run_hook("cat notas.txt > AGENTS.md")
    assert result.returncode == 2

    result = run_hook("echo 'x' | tee AGENTS.md")
    assert result.returncode == 2
