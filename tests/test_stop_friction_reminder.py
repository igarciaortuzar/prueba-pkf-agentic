"""Tests del hook `Stop` de recordatorio de fricciones (ADR-005).

Se invoca el hook como subproceso (mismo patron que
tests/test_protect_bash_writes.py): JSON del evento por stdin, se evalua el
codigo de salida y stderr. El `transcript_path` se simula escribiendo un
JSONL temporal con el mismo formato real verificado durante la
implementacion (bloques `tool_use` dentro de `message.content`, con `name`
e `input.file_path`) -- ver docstring de
`.claude/hooks/stop_friction_reminder.py`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = ROOT / ".claude" / "hooks" / "stop_friction_reminder.py"


def _tool_use_line(tool_name: str, file_path: str) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": tool_name,
                        "input": {"file_path": file_path, "content": "x"},
                    }
                ]
            },
        }
    )


def write_transcript(tmp_path: Path, lines: list[str]) -> Path:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return transcript


def run_hook(
    transcript_path: str,
    stop_hook_active: bool = False,
    session_id: str = "test-session",
) -> subprocess.CompletedProcess:
    event = {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "stop_hook_active": stop_hook_active,
    }
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )


def test_no_relevant_edits_exits_silently(tmp_path):
    lines = [
        _tool_use_line("Edit", "/home/user/prueba-pkf-agentic/app/db.py"),
        _tool_use_line("Read", "/home/user/prueba-pkf-agentic/README.md"),
    ]
    transcript = write_transcript(tmp_path, lines)
    result = run_hook(str(transcript))
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


def test_edit_to_specs_triggers_reminder(tmp_path):
    lines = [
        _tool_use_line("Write", "/home/user/prueba-pkf-agentic/specs/mi-slug.md"),
    ]
    transcript = write_transcript(tmp_path, lines)
    result = run_hook(str(transcript))
    assert result.returncode == 2
    assert "friccion" in result.stderr.lower()
    assert "friction-log.md" in result.stderr


def test_edit_to_draft_adr_triggers_reminder(tmp_path):
    lines = [
        _tool_use_line(
            "Edit", "/home/user/prueba-pkf-agentic/docs/adr/DRAFT-mi-slug.md"
        ),
    ]
    transcript = write_transcript(tmp_path, lines)
    result = run_hook(str(transcript))
    assert result.returncode == 2
    assert "friction-log.md" in result.stderr


def test_edit_to_business_rules_triggers_reminder(tmp_path):
    lines = [
        _tool_use_line(
            "Edit", "/home/user/prueba-pkf-agentic/docs/business-rules.md"
        ),
    ]
    transcript = write_transcript(tmp_path, lines)
    result = run_hook(str(transcript))
    assert result.returncode == 2


def test_accepted_adr_does_not_trigger_reminder(tmp_path):
    # Un ADR ya aceptado (ADR-0XX-slug.md) no es DRAFT-*.md: no es la señal
    # que este hook busca (el hook protege promocion, no ADRs ya aceptados).
    lines = [
        _tool_use_line(
            "Edit",
            "/home/user/prueba-pkf-agentic/docs/adr/ADR-005-captura-automatica-fricciones.md",
        ),
    ]
    transcript = write_transcript(tmp_path, lines)
    result = run_hook(str(transcript))
    assert result.returncode == 0
    assert result.stderr == ""


def test_stop_hook_active_suppresses_reminder_even_with_relevant_edits(tmp_path):
    lines = [
        _tool_use_line("Write", "/home/user/prueba-pkf-agentic/specs/mi-slug.md"),
    ]
    transcript = write_transcript(tmp_path, lines)
    result = run_hook(str(transcript), stop_hook_active=True)
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


def test_nonexistent_transcript_path_does_not_block(tmp_path):
    missing = tmp_path / "does-not-exist.jsonl"
    result = run_hook(str(missing))
    assert result.returncode == 0
    assert result.stderr == ""


def test_invalid_json_in_transcript_does_not_block(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("{ esto no es json valido\n", encoding="utf-8")
    result = run_hook(str(transcript))
    assert result.returncode == 0
    assert result.stderr == ""


def test_invalid_stdin_json_does_not_block(tmp_path):
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="{ esto tampoco es json valido",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_missing_transcript_path_field_does_not_block():
    event = {"session_id": "x", "stop_hook_active": False}
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_ignores_non_tool_use_lines_and_other_entry_types(tmp_path):
    lines = [
        json.dumps({"type": "queue-operation", "operation": "enqueue"}),
        json.dumps({"type": "system", "content": "algo"}),
        json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "content": "resultado, no tool_use"}
                    ]
                },
            }
        ),
    ]
    transcript = write_transcript(tmp_path, lines)
    result = run_hook(str(transcript))
    assert result.returncode == 0
    assert result.stderr == ""


def test_real_transcript_format_from_this_session_detects_signal(tmp_path):
    """Regresion contra el formato real verificado durante la
    implementacion: linea JSONL con type=assistant, message.content=[...],
    bloque tool_use con name=Write/Edit e input.file_path anidado (no un
    tool_name/file_path a nivel raiz de la linea, como si fuera el payload
    de PreToolUse)."""
    real_format_line = json.dumps(
        {
            "parentUuid": "abc",
            "isSidechain": False,
            "message": {
                "model": "claude-sonnet-5",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_test",
                        "name": "Write",
                        "input": {
                            "file_path": "/home/user/prueba-pkf-agentic/specs/algo.md",
                            "content": "...",
                        },
                        "caller": {"type": "direct"},
                    }
                ],
            },
            "requestId": "req_test",
            "type": "assistant",
            "uuid": "def",
            "timestamp": "2026-07-07T00:00:00Z",
        }
    )
    transcript = write_transcript(tmp_path, [real_format_line])
    result = run_hook(str(transcript))
    assert result.returncode == 2
