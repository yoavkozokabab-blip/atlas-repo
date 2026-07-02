"""Tests for minimal SESSION.md / CHECKPOINT.md handoff memory."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import agent_files as af
from jarvis_desktop import repository_memory as rm
from jarvis_desktop import session_handoff as sh


def _repo_memory(repo_path, freshness="fresh"):
    mem = {
        "version": rm.MEMORY_VERSION,
        "repo_name": "demo",
        "scan_signature": "scan-123",
        "memory_hash": "hash-123",
        "freshness_status": freshness,
    }
    return mem


def _events():
    return {
        "timestamp": "2026-06-14T10:00:00Z",
        "current_task": "Improve memory handoff",
        "completed_work": ["Added session generator"],
        "changed_files": ["jarvis_desktop/session_handoff.py"],
        "commands_run": ["py -3 -m pytest jarvis_desktop/tests/test_session_handoff_memory.py"],
        "tests_run": ["session handoff tests"],
        "failures": ["Initial stale freshness wording was unclear"],
        "blockers": ["No live session events beyond explicit input"],
        "next_actions": ["Run validation harness"],
        "do_not_repeat": ["Do not infer work from git status"],
    }


def test_session_md_is_generated(tmp_path):
    session = sh.build_session_memory(_repo_memory(tmp_path), _events())
    res = sh.AtlasSessionMemoryGenerator(session).write(str(tmp_path), "session")

    text = (tmp_path / "SESSION.md").read_text(encoding="utf-8")
    assert res["action"] == "created"
    assert af.MANAGED_BEGIN in text
    assert "Improve memory handoff" in text
    assert "Atlas-generated handoff summary" in text


def test_checkpoint_md_generated_and_updated(tmp_path):
    session = sh.build_session_memory(_repo_memory(tmp_path), _events())
    gen = sh.AtlasSessionMemoryGenerator(session)
    gen.write(str(tmp_path), "checkpoint")

    updated_events = _events()
    updated_events["next_actions"] = ["Review MCP decision"]
    updated = sh.build_session_memory(_repo_memory(tmp_path), updated_events)
    res = sh.AtlasSessionMemoryGenerator(updated).write(str(tmp_path), "checkpoint")
    text = (tmp_path / "CHECKPOINT.md").read_text(encoding="utf-8")

    assert res["action"] == "updated"
    assert "Review MCP decision" in text


def test_session_human_content_preserved(tmp_path):
    before = "# Human session notes\n\nKeep this.\n\n"
    after = "\n## Manual note\n\nStill here.\n"
    (tmp_path / "SESSION.md").write_text(before + af.wrap_block("OLD") + after, encoding="utf-8")

    session = sh.build_session_memory(_repo_memory(tmp_path), _events())
    sh.AtlasSessionMemoryGenerator(session).write(str(tmp_path), "session")
    text = (tmp_path / "SESSION.md").read_text(encoding="utf-8")

    assert text.startswith(before)
    assert text.rstrip().endswith(after.rstrip())
    assert "OLD" not in text
    assert text.count(af.MANAGED_BEGIN) == 1


def test_session_update_idempotent(tmp_path):
    session = sh.build_session_memory(_repo_memory(tmp_path), _events())
    gen = sh.AtlasSessionMemoryGenerator(session)
    gen.write(str(tmp_path), "session")
    second = gen.write(str(tmp_path), "session")
    assert second["action"] == "unchanged"


def test_stale_repository_memory_blocks_freshness_claim(tmp_path):
    session = sh.build_session_memory(_repo_memory(tmp_path, freshness="stale"), _events())
    body = sh.generate_session_md(session)

    assert "Repository memory freshness: stale" in body
    assert "does not claim" in body
    assert "Repository memory freshness: fresh" not in body


def test_empty_session_emits_no_active_session(tmp_path):
    session = sh.build_session_memory(_repo_memory(tmp_path), {})
    body = sh.generate_session_md(session)

    assert session["active"] is False
    assert "No active session events were provided" in body
    assert "Changed files" not in body


def test_changed_files_and_tests_from_explicit_input(tmp_path):
    events = {
        "current_task": "Validate handoff",
        "changed_files": ["a.py", "b.py", "a.py"],
        "tests_run": ["pytest a", "pytest b"],
    }
    session = sh.build_session_memory(_repo_memory(tmp_path), events)
    body = sh.generate_session_md(session)

    assert session["changed_files"] == ["a.py", "b.py"]
    assert session["tests_run"] == ["pytest a", "pytest b"]
    assert "- a.py" in body
    assert "- pytest a" in body
