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
